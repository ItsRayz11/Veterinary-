import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.core.models import AuditLog
from apps.countries.models import Country
from apps.education.models import Question, QuestionReport, Subject, Topic
from apps.pharma.models import Generic, Product, ProductPack
from apps.pricing.models import PriceSubmission, SubmissionKind
from apps.sources.models import Source, SourceLink


@pytest.fixture
def catalog(db):
    call_command("seed_dev_catalog")


def client_for(role, name=None):
    user = User.objects.create_user(name or f"u-{role}", password="x", role=role)
    c = APIClient()
    c.force_login(user)
    return c, user


def test_staff_endpoints_reject_anonymous_and_ordinary_users(catalog):
    assert APIClient().get("/api/v1/staff/summary/").status_code in (401, 403)
    c, _ = client_for(Role.STUDENT)
    for url in (
        "/api/v1/staff/summary/",
        "/api/v1/staff/review-queue/",
        "/api/v1/staff/price-submissions/",
        "/api/v1/staff/audit-log/",
    ):
        assert c.get(url).status_code == 403


def test_queue_lists_unreviewed_records_and_summary_counts(catalog):
    c, _ = client_for(Role.EDITOR)
    rows = c.get("/api/v1/staff/review-queue/").json()["results"]
    assert rows and all(r["review_status"] != "verified" for r in rows)
    counts = c.get("/api/v1/staff/summary/").json()["review_queue"]
    assert counts.get("pharma.generic", 0) >= 1


def test_editor_cannot_sign_off_and_dev_data_can_never_be_verified(catalog):
    generic = Generic.objects.filter(is_development_data=True).first()
    src = Source.objects.create(source_type="other", title="Label", url="https://example.org")
    SourceLink.objects.create(source=src, target=generic)
    url = f"/api/v1/staff/review-queue/pharma.generic/{generic.pk}/status/"
    editor, _ = client_for(Role.EDITOR)
    r = editor.post(url, {"status": "verified"}, format="json")
    assert r.status_code == 403
    vet, _ = client_for(Role.VET_REVIEWER)
    r = vet.post(url, {"status": "verified"}, format="json")
    assert r.status_code == 400  # source missing and/or development data
    generic.refresh_from_db()
    assert generic.review_status != "verified"


def test_unknown_model_status_and_record_are_rejected(catalog):
    c, _ = client_for(Role.ADMIN)
    assert (
        c.post(
            "/api/v1/staff/review-queue/nope.model/1/status/", {"status": "verified"}
        ).status_code
        == 404
    )
    generic = Generic.objects.first()
    url = f"/api/v1/staff/review-queue/pharma.generic/{generic.pk}/status/"
    assert c.post(url, {"status": "bogus"}, format="json").status_code == 400


def test_status_change_writes_audit_and_shows_in_history(catalog):
    generic = Generic.objects.filter(is_development_data=True).first()
    src = Source.objects.create(source_type="other", title="Label", url="https://example.org")

    SourceLink.objects.create(source=src, target=generic)
    c, user = client_for(Role.ADMIN)
    r = c.post(
        f"/api/v1/staff/review-queue/pharma.generic/{generic.pk}/status/",
        {"status": "source_found_pending_review", "reason": "label found"},
        format="json",
    )
    assert r.status_code == 200
    assert AuditLog.objects.filter(actor=user, action="review_status_changed").exists()
    hist = c.get(f"/api/v1/staff/review-queue/pharma.generic/{generic.pk}/history/").json()
    fields = [ch["field"] for v in hist["versions"] for ch in v["changes"]]
    assert "review_status" in fields


@pytest.fixture
def submission(catalog):
    product = Product.objects.get(slug="dev-enro-1")
    author = User.objects.create_user("author", password="x")
    return PriceSubmission.objects.create(
        kind=SubmissionKind.NEW_PRICE,
        pack=ProductPack.objects.get(product=product),
        country=Country.objects.get(iso2="PK"),
        currency="PKR",
        price_type="retail",
        amount="150.00",
        submitted_by=author,
    )


def test_only_moderators_moderate_prices_and_reject_needs_reason(submission):
    editor, _ = client_for(Role.EDITOR)
    assert editor.get("/api/v1/staff/price-submissions/").status_code == 403
    mod, _ = client_for(Role.MODERATOR)
    listed = mod.get("/api/v1/staff/price-submissions/").json()["results"]
    assert [s["id"] for s in listed] == [submission.pk]
    url = f"/api/v1/staff/price-submissions/{submission.pk}"
    assert mod.post(f"{url}/reject/", {"note": ""}, format="json").status_code == 400
    assert mod.post(f"{url}/approve/", {}, format="json").status_code == 200
    assert mod.post(f"{url}/approve/", {}, format="json").status_code == 400  # already done
    assert mod.post(f"{url}/explode/", {}, format="json").status_code == 400


def test_moderator_cannot_approve_own_submission(submission):
    mod, user = client_for(Role.MODERATOR)
    submission.submitted_by = user
    submission.save()
    r = mod.post(f"/api/v1/staff/price-submissions/{submission.pk}/approve/", {}, format="json")
    assert r.status_code == 403


def test_question_reports_resolve_and_audit_log_is_admin_only(catalog):
    subject = Subject.objects.create(name="Pharm", slug="pharm")
    topic = Topic.objects.create(subject=subject, name="T", slug="t")
    q = Question.objects.create(topic=topic, stem="Which drug?")
    reporter = User.objects.create_user("rep", password="x")
    report = QuestionReport.objects.create(question=q, reporter=reporter, message="wrong key")
    mod, _ = client_for(Role.MODERATOR)
    assert len(mod.get("/api/v1/staff/question-reports/").json()["results"]) == 1
    assert (
        mod.post(
            f"/api/v1/staff/question-reports/{report.pk}/resolve/", {}, format="json"
        ).status_code
        == 200
    )
    assert mod.get("/api/v1/staff/question-reports/").json()["results"] == []
    assert mod.get("/api/v1/staff/audit-log/").status_code == 403
    admin, _ = client_for(Role.ADMIN)
    log = admin.get("/api/v1/staff/audit-log/").json()["results"]
    assert any(a["action"] == "question_report_resolved" for a in log)


def test_automation_status_and_manual_run_permissions(catalog):
    editor, _ = client_for(Role.EDITOR)
    data = editor.get("/api/v1/staff/automation/").json()
    assert data["can_run"] is False and "link-check" in data["tasks"]
    assert editor.post("/api/v1/staff/automation/run/feeds/", {}, format="json").status_code == 403
    admin, _ = client_for(Role.ADMIN)
    r = admin.post("/api/v1/staff/automation/run/feeds/", {}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert admin.post("/api/v1/staff/automation/run/nope/", {}, format="json").status_code == 404
    assert AuditLog.objects.filter(action="automation_run_manually").exists()
    assert admin.get("/api/v1/staff/automation/").json()["runs"][0]["task"] == "feeds"


def test_summary_gives_staff_the_configured_admin_path(catalog, settings):
    settings.ADMIN_URL = "private-path/"
    editor, _ = client_for(Role.EDITOR)
    assert editor.get("/api/v1/staff/summary/").json()["admin_url"] == "/private-path/"
    assert APIClient().get("/api/v1/staff/summary/").status_code in (401, 403)  # never public


def test_queue_search_and_paging(catalog):
    c, _ = client_for(Role.EDITOR)
    everything = c.get("/api/v1/staff/review-queue/").json()
    assert everything["count"] >= 7 and everything["page"] == 1
    hit = c.get("/api/v1/staff/review-queue/?q=enrofloxacin").json()
    assert hit["count"] >= 1
    assert all("nro" in r["label"].lower() or r["model"] for r in hit["results"])
    assert c.get("/api/v1/staff/review-queue/?q=zzz-no-such-thing").json()["results"] == []
    # Paging: a page past the end is empty, never an error; junk page numbers fall back to 1.
    assert c.get("/api/v1/staff/review-queue/?page=999").json()["results"] == []
    assert c.get("/api/v1/staff/review-queue/?page=abc").json()["page"] == 1
    # Filtering to one model only returns that model.
    only = c.get("/api/v1/staff/review-queue/?model=pharma.generic").json()["results"]
    assert only and {r["model"] for r in only} == {"pharma.generic"}


def test_queue_pages_do_not_overlap(catalog, settings):
    from apps.staff import services

    services.PAGE_SIZE = 3
    try:
        c, _ = client_for(Role.EDITOR)
        p1 = c.get("/api/v1/staff/review-queue/?page=1").json()["results"]
        p2 = c.get("/api/v1/staff/review-queue/?page=2").json()["results"]
        keys = {(r["model"], r["id"]) for r in p1} & {(r["model"], r["id"]) for r in p2}
        assert len(p1) == 3 and p2 and not keys
    finally:
        services.PAGE_SIZE = 25


def test_record_detail_shows_fields_and_sources(catalog):
    generic = Generic.objects.filter(is_development_data=True).first()
    src = Source.objects.create(
        source_type="other", title="Label", url="https://example.org", license_note="n"
    )
    from django.contrib.contenttypes.models import ContentType

    SourceLink.objects.create(
        source=src, content_type=ContentType.objects.get_for_model(generic), object_id=generic.pk
    )
    c, _ = client_for(Role.EDITOR)
    d = c.get(f"/api/v1/staff/review-queue/pharma.generic/{generic.pk}/").json()
    assert d["label"] and any(f["field"] == "Name" for f in d["fields"])
    assert d["sources"][0]["title"] == "Label"
    assert c.get("/api/v1/staff/review-queue/pharma.generic/999999/").status_code == 404
    assert c.get("/api/v1/staff/review-queue/nope.model/1/").status_code == 404
    assert APIClient().get(
        f"/api/v1/staff/review-queue/pharma.generic/{generic.pk}/"
    ).status_code in (401, 403)
