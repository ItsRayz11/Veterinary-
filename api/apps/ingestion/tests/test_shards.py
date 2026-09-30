"""Parallel approval: shards partition the work, and a lost race is retried, never lost."""

import pytest
from django.db import IntegrityError

from apps.ingestion import services
from apps.ingestion.models import RowStatus
from apps.ingestion.tests.test_drap_adapters import env  # noqa: F401
from apps.ingestion.tests.test_ingestion import stage
from apps.pharma.models import Product

HEADER = "brand_name,generic_name,manufacturer,registration_number\n"


def csv(n):
    return HEADER + "".join(f"Shard-{i},Enrofloxacin,Shard Co {i % 3},S-{i}\n" for i in range(n))


def test_shards_partition_the_rows_with_no_overlap_and_no_gaps(env):  # noqa: F811
    batch = stage(env, csv(12))
    seen = []
    for index in range(3):
        before = set(batch.rows.filter(status=RowStatus.APPROVED).values_list("id", flat=True))
        result = services.approve_clean(batch, env["user"], limit=100, shard=(index, 3))
        assert result["skipped"] == 0 and result["remaining"] == 0
        after = set(batch.rows.filter(status=RowStatus.APPROVED).values_list("id", flat=True))
        mine = after - before
        assert mine and all(i % 3 == index for i in mine)
        seen.append(mine)
    assert sum(len(s) for s in seen) == 12 and len(set().union(*seen)) == 12
    assert Product.objects.filter(brand_name__startswith="Shard-").count() == 12


def test_a_shard_only_reports_its_own_remaining_rows(env):  # noqa: F811
    batch = stage(env, csv(9))
    first = services.approve_clean(batch, env["user"], limit=1, shard=(0, 3))
    assert first["approved"] == 1 and first["remaining"] == 2  # 3 rows in shard 0, one done
    assert batch.rows.filter(status=RowStatus.PENDING).count() == 8  # others untouched


def test_a_lost_creation_race_is_retried_and_leaves_the_row_pending(env, monkeypatch):  # noqa: F811
    batch = stage(env, csv(2))
    real = services.approve_row
    calls = {"n": 0}

    def flaky(row, by, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("duplicate key value violates unique constraint")
        return real(row, by, **kw)

    monkeypatch.setattr(services, "approve_row", flaky)
    first = services.approve_clean(batch, env["user"], limit=10)
    assert first["retried"] == 1 and first["approved"] == 1 and first["remaining"] == 1
    second = services.approve_clean(batch, env["user"], limit=10)  # the next pass finishes it
    assert second["approved"] == 1 and second["remaining"] == 0
    assert Product.objects.filter(brand_name__startswith="Shard-").count() == 2


def test_command_rejects_a_malformed_shard(env, tmp_path):  # noqa: F811
    from django.core.management import CommandError, call_command

    f = tmp_path / "p.csv"
    f.write_text(csv(1), encoding="utf-8")
    for bad in ("3", "a/b", "5/3", "-1/2"):
        with pytest.raises(CommandError, match="--shard"):
            call_command(
                "import_products",
                "standard",
                str(f),
                "--country",
                "PK",
                "--source-title",
                "T",
                "--publisher",
                "P",
                "--license-note",
                "n",
                f"--shard={bad}",
            )
