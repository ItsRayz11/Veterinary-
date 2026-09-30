from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.opportunities import services
from apps.opportunities.models import Job, ListingStatus, Scholarship

TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _countries(db):
    call_command("seed_reference")


def user(name, role=Role.REGISTERED):
    return User.objects.create_user(name, password="x", role=role)


def client(u):
    c = APIClient()
    c.force_login(u)
    return c


JOB = {
    "title": "Large animal veterinarian",
    "organization": "Example Dairy Ltd",
    "country": "PK",
    "city": "Lahore",
    "job_type": "full_time",
    "description": "Ambulatory herd health.",
    "apply_url": "https://example.org/apply",
}


def make_job(author, **kw):
    fields = dict(JOB, country=None) | kw
    return Job.objects.create(submitted_by=author, **fields)


def test_submission_is_pending_and_hidden_until_approved():
    author, mod = user("author"), user("mod", Role.MODERATOR)
    r = client(author).post("/api/v1/listings/jobs/submit/", JOB, format="json")
    assert r.status_code == 201 and r.json()["status"] == "pending"
    job = Job.objects.get()
    assert APIClient().get("/api/v1/listings/jobs/").json() == []
    assert APIClient().get(f"/api/v1/listings/jobs/{job.pk}/").status_code == 404
    services.approve(job, mod)
    shown = APIClient().get("/api/v1/listings/jobs/").json()
    assert [j["title"] for j in shown] == ["Large animal veterinarian"]
    assert shown[0]["country"] == "PK"


def test_anonymous_cannot_submit_and_input_is_validated():
    assert APIClient().post("/api/v1/listings/jobs/submit/", JOB, format="json").status_code in (
        401,
        403,
    )
    c = client(user("u"))
    bad_url = c.post(
        "/api/v1/listings/jobs/submit/", {**JOB, "apply_url": "javascript:alert(1)"}, format="json"
    )
    assert bad_url.status_code == 400
    past = c.post(
        "/api/v1/listings/jobs/submit/",
        {**JOB, "closes_on": str(TODAY - timedelta(days=1))},
        format="json",
    )
    assert past.status_code == 400
    assert c.post("/api/v1/listings/nope/submit/", JOB, format="json").status_code == 400
    assert (
        c.post(
            "/api/v1/listings/jobs/submit/", {**JOB, "job_type": "slave"}, format="json"
        ).status_code
        == 400
    )


def test_pending_cap_per_user():
    author = user("busy")
    for i in range(services.MAX_PENDING_PER_USER):
        make_job(author, title=f"J{i}")
    r = client(author).post("/api/v1/listings/jobs/submit/", JOB, format="json")
    assert r.status_code == 400 and "waiting for review" in str(r.json())


def test_moderation_rules():
    author, mod, other = user("a"), user("m", Role.MODERATOR), user("o")
    job = make_job(author)
    with pytest.raises(PermissionDenied):
        services.approve(job, other)
    own = make_job(mod, title="Mine")
    with pytest.raises(PermissionDenied, match="own"):
        services.approve(own, mod)
    with pytest.raises(ValidationError, match="reason"):
        services.reject(job, mod, " ")
    services.approve(job, mod, "looks fine")
    with pytest.raises(ValidationError, match="already"):
        services.approve(job, mod)
    job.refresh_from_db()
    assert job.status == ListingStatus.APPROVED
    assert job.expires_on == TODAY + timedelta(days=90)  # no closing date -> default lifetime


def test_expiry_uses_closing_date_and_expired_listing_disappears():
    author, mod = user("a"), user("m", Role.MODERATOR)
    job = make_job(author, closes_on=TODAY + timedelta(days=5))
    services.approve(job, mod)
    job.refresh_from_db()
    assert job.expires_on == TODAY + timedelta(days=5)
    assert Job.objects.public().count() == 1
    Job.objects.filter(pk=job.pk).update(expires_on=TODAY - timedelta(days=1))
    assert Job.objects.public().count() == 0
    late = make_job(author, title="Late", closes_on=TODAY - timedelta(days=1))
    with pytest.raises(ValidationError, match="passed"):
        services.approve(late, mod)


def test_three_distinct_reports_send_a_listing_back_to_review():
    author, mod = user("a"), user("m", Role.MODERATOR)
    job = make_job(author)
    services.approve(job, mod)
    reporters = [user(f"r{i}") for i in range(3)]
    with pytest.raises(ValidationError, match="own"):
        services.report(job, author, "spam")
    services.report(job, reporters[0], "looks like a scam")
    with pytest.raises(ValidationError, match="already"):
        services.report(job, reporters[0], "again")
    services.report(job, reporters[1], "dead link")
    job.refresh_from_db()
    assert job.status == ListingStatus.APPROVED
    services.report(job, reporters[2], "fake")
    job.refresh_from_db()
    assert job.status == ListingStatus.PENDING and "3 user reports" in job.moderation_note
    assert Job.objects.public().count() == 0
    with pytest.raises(ValidationError, match="live"):
        services.report(job, user("late"), "too late")


def test_scholarship_filters_and_staff_endpoints_permissions():
    author, mod = user("a"), user("m", Role.MODERATOR)
    sch = Scholarship.objects.create(
        submitted_by=author,
        title="PhD in poultry health",
        organization="Univ",
        level="phd",
        funding="full",
        description="x",
        apply_url="https://example.org/s",
    )
    services.approve(sch, mod)
    api = APIClient()
    assert len(api.get("/api/v1/listings/scholarships/?level=phd").json()) == 1
    assert api.get("/api/v1/listings/scholarships/?level=dvm").json() == []
    assert len(api.get("/api/v1/listings/scholarships/?q=poultry").json()) == 1
    assert client(user("stu", Role.STUDENT)).get("/api/v1/staff/listings/").status_code == 403
    job = make_job(author)
    m = client(mod)
    pending = m.get("/api/v1/staff/listings/").json()["results"]
    assert [p["id"] for p in pending] == [job.pk]
    assert (
        m.post(
            f"/api/v1/staff/listings/jobs/{job.pk}/reject/", {"note": ""}, format="json"
        ).status_code
        == 400
    )
    assert (
        m.post(f"/api/v1/staff/listings/jobs/{job.pk}/approve/", {}, format="json").status_code
        == 200
    )
    assert (
        m.post(f"/api/v1/staff/listings/jobs/{job.pk}/zap/", {}, format="json").status_code == 400
    )
