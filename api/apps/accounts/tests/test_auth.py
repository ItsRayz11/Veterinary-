import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User

PW = "S3cure-pass-phrase!"


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
def test_register_login_me_logout(api):
    r = api.post("/api/v1/auth/register/", {"username": "a", "email": "a@x.com", "password": PW})
    assert r.status_code == 201 and r.json()["role"] == Role.REGISTERED
    assert api.get("/api/v1/auth/me/").json()["username"] == "a"
    assert api.post("/api/v1/auth/logout/").status_code == 204
    assert api.get("/api/v1/auth/me/").status_code in (401, 403)
    assert api.post("/api/v1/auth/login/", {"username": "a", "password": PW}).status_code == 200


@pytest.mark.django_db
def test_cannot_self_assign_privileged_role(api):
    r = api.post(
        "/api/v1/auth/register/",
        {"username": "b", "email": "b@x.com", "password": PW, "role": "admin"},
    )
    assert r.status_code == 400
    assert not User.objects.filter(username="b").exists()


@pytest.mark.django_db
def test_bad_login_uses_error_envelope(api):
    r = api.post("/api/v1/auth/login/", {"username": "nope", "password": "x"})
    assert r.status_code == 400 and "error" in r.json()


@pytest.mark.django_db
def test_weak_password_rejected(api):
    r = api.post("/api/v1/auth/register/", {"username": "c", "email": "c@x.com", "password": "123"})
    assert r.status_code == 400
