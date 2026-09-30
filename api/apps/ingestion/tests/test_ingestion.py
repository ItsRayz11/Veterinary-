import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.companies.models import Company
from apps.countries.models import Country
from apps.ingestion import services
from apps.ingestion.models import RowStatus
from apps.pharma.models import Generic, Product, ProductRegistration
from apps.sources.models import sources_for

SOURCE = {
    "title": "Test registry export",
    "publisher": "Test authority",
    "url": "https://example.org/registry.csv",
    "license_note": "Test note: fictional data for tests",
    "source_type": "regulatory",
}

CSV = (
    "Brand,Generic,Company,Reg No,Registration Status\n"
    "Zyra-Test,Enrofloxacin,Acme Vet Ltd,R-1,registered\n"
    "Zyra-Test,Enrofloxacin,Acme Vet Ltd,R-2,registered\n"  # same brand+company twice
    ",Enrofloxacin,Acme Vet Ltd,R-3,\n"  # missing brand
    "Odd-Status,Enrofloxacin,Acme Vet Ltd,R-4,maybe\n"  # bad status
)


@pytest.fixture
def env(db):
    call_command("seed_dev_catalog")
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    return {"pk": Country.objects.get(iso2="PK"), "user": editor}


def stage(env, text=CSV, **kw):
    return services.stage_batch(
        user=env["user"], country=env["pk"], source_data=SOURCE, csv_text=text, **kw
    )


def test_parse_rejects_bad_files():
    for text, fragment in (
        ("", "empty"),
        ("brand_name,generic_name\nA,B\n", "manufacturer"),
        ("brand_name,generic_name,manufacturer\n", "no rows"),
    ):
        with pytest.raises(ValidationError, match=fragment):
            services.parse_csv(text)


def test_staging_flags_errors_and_requires_provenance(env):
    batch = stage(env)
    statuses = list(batch.rows.values_list("status", flat=True))
    assert statuses == [
        RowStatus.PENDING,
        RowStatus.PENDING,
        RowStatus.ERROR,
        RowStatus.ERROR,
    ]
    assert batch.rows.first().matched_generic.slug == "enrofloxacin"  # matched, not duplicated
    assert Product.objects.filter(brand_name="Zyra-Test").count() == 0  # nothing created yet
    bad = {**SOURCE, "license_note": ""}
    with pytest.raises(ValidationError, match="licence"):
        services.stage_batch(
            user=env["user"], country=env["pk"], source_data=bad, csv_text=CSV.replace("R-", "Q-")
        )
    with pytest.raises(ValidationError, match="already imported"):
        stage(env)


def test_approve_creates_only_unreviewed_records_with_source(env):
    batch = stage(env)
    row = batch.rows.get(row_number=1)
    services.approve_row(row, env["user"])
    product = Product.objects.get(brand_name="Zyra-Test")
    assert product.review_status == "needs_verification" and not product.is_public
    assert product.generic.slug == "enrofloxacin"  # reused the existing generic
    company = Company.objects.get(name="Acme Vet Ltd")
    assert company.review_status == "needs_verification"
    reg = ProductRegistration.objects.get(registration_number="R-1")
    assert reg.status == "registered" and reg.review_status == "needs_verification"
    for obj in (product, company, reg):
        assert sources_for(obj).filter(title=SOURCE["title"]).exists()
    assert Generic.objects.filter(normalized_name="enrofloxacin").count() == 1


def test_second_row_for_same_brand_becomes_duplicate_and_bulk_approve_skips_bad_rows(env):
    batch = stage(env)
    result = services.approve_clean(batch, env["user"])
    assert result == {"approved": 1, "skipped": 1, "remaining": 0}
    dup = batch.rows.get(row_number=2)
    dup.refresh_from_db()
    with pytest.raises(ValidationError, match="already exists"):
        services.approve_row(dup, env["user"])
    with pytest.raises(ValidationError, match="reason"):
        services.reject_row(dup, env["user"], "  ")
    services.reject_row(dup, env["user"], "same product listed twice")
    for n in (3, 4):
        services.reject_row(batch.rows.get(row_number=n), env["user"], "invalid")
    batch.refresh_from_db()
    assert batch.status == "completed"


def test_registration_number_conflict_is_flagged(env):
    stage(
        env,
        "brand_name,generic_name,manufacturer,registration_number\nA-One,Enrofloxacin,Acme,R-9\n",
    )
    second = stage(
        env,
        "brand_name,generic_name,manufacturer,registration_number\nB-Two,Enrofloxacin,Beta,R-9\n",
    )
    services.approve_clean(second.rows.first().batch, env["user"])
    first_batch = services.ImportBatch.objects.order_by("id").first()
    services.approve_clean(first_batch, env["user"])
    assert ProductRegistration.objects.filter(registration_number="R-9").count() == 1


def api_client(role):
    user = User.objects.create_user(f"u-{role}", password="x", role=role)
    c = APIClient()
    c.force_login(user)
    return c


def test_import_api_permissions_and_flow(env):
    payload = {"country": "PK", "source": SOURCE, "csv_text": CSV, "file_name": "x.csv"}
    assert APIClient().post("/api/v1/staff/imports/", payload, format="json").status_code in (
        401,
        403,
    )
    assert (
        api_client(Role.STUDENT).post("/api/v1/staff/imports/", payload, format="json").status_code
        == 403
    )
    editor = api_client(Role.EDITOR)
    r = editor.post("/api/v1/staff/imports/", payload, format="json")
    assert r.status_code == 201 and r.json()["counts"] == {"pending": 2, "error": 2}
    batch_id = r.json()["id"]
    assert editor.post("/api/v1/staff/imports/", payload, format="json").status_code == 400
    detail = editor.get(f"/api/v1/staff/imports/{batch_id}/?status=pending").json()
    assert len(detail["rows"]) == 2 and detail["rows"][0]["generic_match"] == "Enrofloxacin"
    first = detail["rows"][0]["id"]
    ok = editor.post(f"/api/v1/staff/imports/{batch_id}/rows/{first}/approve/", {}, format="json")
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    bad = editor.post(f"/api/v1/staff/imports/{batch_id}/rows/{first}/nope/", {}, format="json")
    assert bad.status_code == 400
    assert editor.get("/api/v1/staff/imports/").json()["results"][0]["id"] == batch_id
    # the imported product is not public
    assert APIClient().get("/api/v1/products/zyra-test/").status_code == 404
