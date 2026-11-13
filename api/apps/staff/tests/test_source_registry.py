import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.automation.models import DataSource
from apps.core.models import AuditLog

URL = "/api/v1/staff/sources/"
BODY = {
    "slug": "demo",
    "name": "Demo regulator",
    "kind": "open_data",
    "landing_url": "https://example.org/data",
    "licence_note": "Open licence per publisher",
    "method": "api",
    "credentials_ref": "DEMO_API_KEY",
    "priority": 5,
}


def client(role):
    u, _ = User.objects.get_or_create(username=f"u-{role}", defaults={"role": role})
    c = APIClient()
    c.force_login(u)
    return c


@pytest.mark.django_db
def test_only_admins_can_read_or_write_registry():
    for role in (Role.EDITOR, Role.MODERATOR, Role.REVIEWER, Role.STUDENT):
        c = client(role)
        assert c.get(URL).status_code == 403
        assert c.post(URL, BODY, format="json").status_code == 403


@pytest.mark.django_db
def test_admin_creates_edits_pauses_and_everything_is_audited():
    c = client(Role.ADMIN)
    r = c.post(URL, BODY, format="json")
    assert r.status_code == 201, r.content
    pk = r.json()["id"]
    assert c.patch(f"{URL}{pk}/", {"priority": 1}, format="json").json()["priority"] == 1
    assert c.post(f"{URL}{pk}/pause/").json()["paused"] is True
    assert c.post(f"{URL}{pk}/check/").status_code == 409  # paused
    assert c.post(f"{URL}{pk}/resume/").json()["paused"] is False
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"source_created", "source_edited", "source_pause", "source_resume"} <= actions


@pytest.mark.django_db
def test_credentials_reference_must_be_a_variable_name_not_a_key():
    c = client(Role.ADMIN)
    r = c.post(URL, {**BODY, "credentials_ref": "sk-live-abc123secret"}, format="json")
    assert r.status_code == 400
    assert not DataSource.objects.filter(slug="demo").exists()


@pytest.mark.django_db
def test_import_cannot_be_enabled_without_confirmed_terms_or_when_restricted():
    c = client(Role.ADMIN)
    r = c.post(
        URL,
        {**BODY, "import_enabled": True, "importer": "x", "data_url": "https://e.org/f"},
        format="json",
    )
    assert r.status_code == 400
    r = c.post(URL, {**BODY, "robots_status": "restricted", "import_enabled": True}, format="json")
    assert r.status_code == 400
