import pytest
from django.core.management import call_command
from django.test import Client
from rest_framework.test import APIClient


def test_openapi_schema_generates_without_warnings(tmp_path):
    out = tmp_path / "schema.yml"
    call_command("spectacular", "--fail-on-warn", file=str(out))
    text = out.read_text(encoding="utf-8")
    assert "/api/v1/staff/imports/" in text and "/api/v1/assistant/ask/" in text


def test_admin_url_is_configurable(settings):
    assert settings.ADMIN_URL.endswith("/")
    assert Client().get(f"/{settings.ADMIN_URL}login/").status_code == 200


def test_csrf_cookie_is_httponly_and_session_cookie_settings(db):
    r = APIClient().get("/api/v1/auth/csrf/")
    cookie = r.cookies["csrftoken"]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
    assert r.json()["csrfToken"]  # the client gets the token from the body instead


def test_oversized_request_body_is_rejected(db, settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 1000
    api = APIClient()
    big = "x" * 5000
    r = api.post("/api/v1/auth/login/", {"username": big, "password": "x"}, format="json")
    assert r.status_code == 400  # request body too large -> bad request, never processed


@pytest.mark.parametrize(
    "path", ["/api/v1/staff/summary/", "/api/v1/staff/imports/", "/api/v1/staff/automation/"]
)
def test_staff_endpoints_never_public(db, path):
    assert APIClient().get(path).status_code in (401, 403)


def test_security_headers_on_api_responses(db):
    r = APIClient().get("/api/v1/health/")
    assert r["X-Content-Type-Options"] == "nosniff"
    assert r["X-Frame-Options"] == "DENY"
    assert r["Referrer-Policy"] == "same-origin"
