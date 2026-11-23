"""Regression: merging duplicate sources must repoint hidden (related_name="+") foreign keys too.

ImportBatch.source and PriceRecord.source are PROTECT keys with no reverse name, so they were not
repointed, and deleting the duplicate raised ProtectedError (this failed every production build's
`backfill_sources` step). All data here is synthetic.
"""

import pytest

from apps.countries.models import Country
from apps.ingestion.models import ImportBatch
from apps.sources import linking
from apps.sources.models import Source

pytestmark = pytest.mark.django_db
URL = "https://example.org/registry"


def _dups():
    keep = Source.objects.create(source_type="other", title="Keep", url=URL)
    dup = Source.objects.create(source_type="other", title="Dup", url=URL + "#x")
    assert keep.canonical_url == dup.canonical_url and keep.pk < dup.pk
    return keep, dup


def test_merge_repoints_import_batches_instead_of_failing():
    country = Country.objects.create(iso2="ZZ", slug="zz", name="Testland", currency_code="ZZZ")
    keep, dup = _dups()
    batch = ImportBatch.objects.create(
        country=country, source=dup, file_name="synthetic.csv", checksum="0" * 64
    )
    out = linking.dedupe_sources()
    assert out["merged"] == 1
    batch.refresh_from_db()
    assert batch.source_id == keep.pk
    assert not Source.objects.filter(pk=dup.pk).exists()


def test_merge_repoints_every_reverse_reference_including_hidden_ones():
    keep, dup = _dups()
    hidden = [
        r.related_model
        for r in Source._meta.get_fields(include_hidden=True)
        if r.auto_created and not r.concrete and (r.one_to_many or r.many_to_one)
    ]
    # Guard: the models that used related_name="+" are among the relations that get repointed.
    assert ImportBatch in hidden
