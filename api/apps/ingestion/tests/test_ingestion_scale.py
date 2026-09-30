"""Import pipeline cost and progress guarantees for large files."""

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.companies.models import Company
from apps.core.models import ReviewStatus
from apps.ingestion import services
from apps.ingestion.models import StagedRecord
from apps.ingestion.tests.test_ingestion import env, stage  # noqa: F401 (env is a fixture)

HEADER = "brand_name,generic_name,manufacturer,registration_number\n"


def _csv(prefix, n, companies=7):
    return HEADER + "".join(
        f"{prefix}-{i},Enrofloxacin,Scale Co {i % companies},{prefix}-R{i}\n" for i in range(n)
    )


def test_staging_cost_does_not_grow_with_the_number_of_rows(env):  # noqa: F811
    with CaptureQueriesContext(connection) as small:
        stage(env, _csv("S", 10))
    with CaptureQueriesContext(connection) as large:
        stage(env, _csv("L", 200))
    # A bulk insert may be split into a few statements by the database; per-row matching would
    # have cost ~4 queries per row (800 here).
    assert len(large) <= len(small) + 8 and len(large) <= 40


def test_bulk_approval_works_in_bounded_chunks_and_always_makes_progress(env):  # noqa: F811
    # six rows; the last repeats brand "C-0" of company "Scale Co 0" (a duplicate once row 1 exists)
    batch = stage(env, _csv("C", 5) + "C-0,Enrofloxacin,Scale Co 0,C-Rdup\n")
    first = services.approve_clean(batch, env["user"], limit=2)
    assert first == {"approved": 2, "skipped": 0, "retried": 0, "remaining": 4}
    second = services.approve_clean(batch, env["user"], limit=2)
    assert second["approved"] == 2 and second["remaining"] == 2
    third = services.approve_clean(batch, env["user"], limit=10)
    assert third["approved"] == 1 and third["skipped"] == 1 and third["remaining"] == 0
    assert batch.rows.filter(status="duplicate").count() == 1
    # nothing is left pending, so a further call is a no-op and the UI can stop
    assert services.approve_clean(batch, env["user"]) == {
        "approved": 0,
        "skipped": 0,
        "retried": 0,
        "remaining": 0,
    }


def test_fast_and_single_row_matching_agree(env):  # noqa: F811
    Company.objects.create(
        name="Existing Co", country=env["pk"], review_status=ReviewStatus.NEEDS_VERIFICATION
    )
    text = (
        HEADER
        + "Fresh,Enrofloxacin,Existing Co,X-1\n"
        + "Fresh,ENROFLOXACIN,existing co,X-2\n"
        + "Other,Unknownium,New Co,X-3\n"
        + "Third,Enrofloxacin,Existing Co,X-1\n"
    )
    batch = stage(env, text)
    fast = list(batch.rows.values_list("status", "matched_generic_id", "matched_company_id"))
    slow = []
    for row in batch.rows.all():
        clone = StagedRecord(
            brand_name=row.brand_name,
            generic_name=row.generic_name,
            manufacturer_name=row.manufacturer_name,
            registration_number=row.registration_number,
            registration_status=row.registration_status,
        )
        services._match(clone, env["pk"])
        slow.append((clone.status, clone.matched_generic_id, clone.matched_company_id))
    assert fast == slow
