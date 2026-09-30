"""Error monitoring: bounded, deduplicated, scrubbed, staff-readable, never personal."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.monitoring import sentry, service
from apps.monitoring.models import ClientError


@pytest.fixture(autouse=True)
def _clean():
    cache.clear()


def report(api, **body):
    return api.post("/api/v1/monitoring/client-errors/", body, format="json")


def test_an_anonymous_browser_can_report_without_csrf_or_login(db):
    api = APIClient(enforce_csrf_checks=True)
    api.force_login(User.objects.create_user("u", password="x"))  # even with a session cookie
    r = report(
        api,
        message="TypeError: x is undefined",
        stack="Error\n at f (app.js:1:1)",
        url="https://site/drugs/x",
    )
    assert r.status_code == 202
    e = ClientError.objects.get()
    assert e.path == "/drugs/x" and e.count == 1


def test_repeats_are_grouped_and_numbers_in_messages_do_not_split_groups(db):
    api = APIClient()
    for i in range(3):
        report(
            api,
            message=f"Failed to load chunk {1000 + i}",
            stack="E\n at a (x.js:1:1)",
            url="/drugs/a",
        )
    assert ClientError.objects.count() == 1 and ClientError.objects.get().count == 3
    report(
        api, message="Failed to load chunk 7", stack="E\n at a (x.js:1:1)", url="/calculators/cri"
    )
    assert ClientError.objects.count() == 2  # different page = different problem


def test_nothing_personal_or_secret_is_stored(db):
    api = APIClient()
    report(
        api,
        message="Login failed for vet@example.org token abcdefghijklmnopqrstuvwxyz0123456789ABCD",
        stack="E\n at x (https://site/?token=abcdefghijklmnopqrstuvwxyz0123456789ABCD)",
        url="https://site/account?email=vet@example.org&session=abc#frag",
    )
    e = ClientError.objects.get()
    blob = f"{e.message} {e.stack} {e.path}"
    assert "vet@example.org" not in blob and "abcdefghijklmnopqrstuvwxyz0123456789ABCD" not in blob
    assert "[email]" in e.message and "[token]" in e.message
    assert e.path == "/account"  # query string and fragment dropped


def test_reports_are_size_limited_and_empty_ones_ignored(db):
    api = APIClient()
    report(api, message="x" * 5000, stack="s" * 50000, url="/" + "p" * 2000)
    e = ClientError.objects.get()
    assert len(e.message) <= 500 and len(e.stack) <= 4000 and len(e.path) <= 300
    assert report(api, message="   ").status_code == 202
    assert ClientError.objects.count() == 1


def test_non_object_bodies_are_rejected(db):
    api = APIClient()
    assert api.post("/api/v1/monitoring/client-errors/", ["x"], format="json").status_code == 400


def test_an_error_that_returns_after_being_resolved_reopens(db):
    service.record(message="boom", url="/a")
    ClientError.objects.update(resolved=True)
    service.record(message="boom", url="/a")
    assert ClientError.objects.get().resolved is False


def test_reporting_is_throttled_per_client(db, settings):
    api = APIClient()
    codes = [report(api, message=f"m{i}", url="/a").status_code for i in range(40)]
    assert 429 in codes and codes[0] == 202


def test_only_staff_can_read_or_resolve_errors(db):
    service.record(message="boom", stack="E\n at x", url="/a")
    error = ClientError.objects.get()
    assert APIClient().get("/api/v1/staff/errors/").status_code in (401, 403)
    student = APIClient()
    student.force_login(User.objects.create_user("s", password="x", role=Role.STUDENT))
    assert student.get("/api/v1/staff/errors/").status_code == 403
    assert student.post(f"/api/v1/staff/errors/{error.pk}/resolve/").status_code == 403
    editor = APIClient()
    editor.force_login(User.objects.create_user("e", password="x", role=Role.EDITOR))
    rows = editor.get("/api/v1/staff/errors/").json()["results"]
    assert rows[0]["message"] == "boom" and rows[0]["count"] == 1
    assert editor.post(f"/api/v1/staff/errors/{error.pk}/resolve/").status_code == 200
    assert editor.get("/api/v1/staff/errors/").json()["results"] == []
    assert len(editor.get("/api/v1/staff/errors/?resolved=1").json()["results"]) == 1
    assert editor.post("/api/v1/staff/errors/99999/resolve/").status_code == 404


# ---------- Sentry (server errors) ----------


def test_sentry_is_off_without_a_dsn():
    assert sentry.init("") is False


def test_events_are_scrubbed_before_sending():
    event = {
        "request": {
            "cookies": {"sessionid": "secret"},
            "data": {"password": "hunter2"},
            "query_string": "email=a@b.c",
            "headers": {
                "Cookie": "sessionid=secret",
                "Authorization": "Bearer x",
                "X-Web-Proxy-Secret": "s",
                "X-Client-IP": "1.2.3.4",
                "User-Agent": "Mozilla",
            },
            "url": "https://api/x",
        },
        "user": {"id": 5, "email": "a@b.c"},
    }
    out = sentry.scrub_event(event)
    assert "user" not in out
    assert set(out["request"]) == {"headers", "url"}
    assert out["request"]["headers"] == {"User-Agent": "Mozilla"}
