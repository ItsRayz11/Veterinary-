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
