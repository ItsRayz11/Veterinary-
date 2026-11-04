"""Role -> Django admin access.

A user's `role` decides which permission group they belong to; staff roles get `is_staff` so they
can sign in to /admin/. Superusers keep everything. Reviewers can edit and approve catalogue and
clinical records but cannot delete them or touch accounts; only the Admin role manages users and
data sources. Two-factor is still required for every staff account (see mfa.py).
"""

from django.contrib.auth.models import Group, Permission

from .models import Role

CATALOGUE = [
    "pharma.generic", "pharma.product", "pharma.productregistration",
    "pharma.registrationspecies", "pharma.drugclass", "pharma.ingredient",
    "pharma.genericsynonym", "pharma.dosageform", "companies.company", "species.species",
    "countries.country", "universities.university", "sources.source",
]  # fmt: skip
CLINICAL = ["clinical.doseregimen", "clinical.interaction", "clinical.clinicalnote",
            "clinical.withdrawalperiod"]  # fmt: skip
READ_ONLY = ["sources.sourcelink", "ingestion.importbatch", "ingestion.stagedrecord",
             "automation.datasource", "automation.jobrun", "core.auditlog"]  # fmt: skip

# role -> {model label -> actions}
RULES = {
    Role.REVIEWER: {**dict.fromkeys(CATALOGUE, ("view", "change")),
                    **dict.fromkeys(READ_ONLY, ("view",))},
    Role.EDITOR: {**dict.fromkeys(CATALOGUE, ("view", "add", "change")),
                  **dict.fromkeys(READ_ONLY, ("view",))},
    Role.VET_REVIEWER: {**dict.fromkeys(CATALOGUE + CLINICAL, ("view", "change")),
                        **dict.fromkeys(READ_ONLY, ("view",))},
    Role.MODERATOR: {**dict.fromkeys(CATALOGUE, ("view",)),
                     **dict.fromkeys(READ_ONLY, ("view",))},
    Role.ADMIN: {**dict.fromkeys(CATALOGUE + CLINICAL, ("view", "add", "change", "delete")),
                 **dict.fromkeys(READ_ONLY, ("view",)),
                 "automation.datasource": ("view", "add", "change"),
                 "accounts.user": ("view", "add", "change")},
}  # fmt: skip
STAFF_ROLES = frozenset(RULES)


def group_name(role: str) -> str:
    return f"Role: {Role(role).label}"


def ensure_groups() -> None:
    for role, rules in RULES.items():
        group, _ = Group.objects.get_or_create(name=group_name(role))
        perms = []
        for label, actions in rules.items():
            app, model = label.split(".")
            codes = [f"{a}_{model}" for a in actions]
            perms += list(
                Permission.objects.filter(content_type__app_label=app, codename__in=codes)
            )
        group.permissions.set(perms)


def sync_user(user) -> None:
    """Put the user in the group for their role and set is_staff accordingly."""
    if user.is_superuser:
        return
    ensure_groups()
    role_groups = Group.objects.filter(name__in=[group_name(r) for r in RULES])
    want_staff = user.role in STAFF_ROLES and user.has_usable_password()
    user.groups.remove(*role_groups)
    if want_staff:
        user.groups.add(Group.objects.get(name=group_name(user.role)))
    if user.is_staff != want_staff:
        type(user).objects.filter(pk=user.pk).update(is_staff=want_staff)
        user.is_staff = want_staff
