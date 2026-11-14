import pytest

from apps.accounts.models import Role, User


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,allowed",
    [
        (Role.VET_REVIEWER, True),
        (Role.ADMIN, True),
        (Role.COMPANY_REP, False),
        (Role.EDITOR, False),
    ],
)
def test_clinical_approval_roles(role, allowed):
    assert User(username="u", role=role).can_approve_clinical is allowed


@pytest.mark.django_db
def test_admin_emails_bootstrap(settings):
    from apps.accounts.roles import promote_if_listed
    from apps.core.models import AuditLog

    settings.ADMIN_EMAILS = ["owner@example.com"]
    other = User.objects.create_user("o", email="other@example.com", password="x")
    owner = User.objects.create_user("w", email="Owner@Example.com", password="x")
    assert promote_if_listed(other) is False
    assert promote_if_listed(owner) is True
    owner.refresh_from_db()
    assert owner.role == Role.ADMIN and owner.is_staff
    assert promote_if_listed(owner) is False
    assert AuditLog.objects.filter(action="admin_bootstrap").count() == 1


@pytest.mark.django_db
def test_admin_emails_promote_on_register(settings, client):
    settings.ADMIN_EMAILS = ["owner@example.com"]
    r = client.post(
        "/api/v1/auth/register/",
        {"username": "newowner", "email": "owner@example.com", "password": "Str0ng-pass-123!"},
        content_type="application/json",
    )
    assert r.status_code == 201
    assert r.json()["role"] == "admin"
