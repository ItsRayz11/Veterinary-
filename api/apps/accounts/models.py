from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    REGISTERED = "registered", "Registered user"
    STUDENT = "student", "Student"
    PROFESSIONAL = "professional", "Professional"
    COMPANY_REP = "company_rep", "Company representative"
    REVIEWER = "reviewer", "Reviewer"
    VET_REVIEWER = "vet_reviewer", "Veterinarian reviewer"
    EDITOR = "editor", "Editor"
    MODERATOR = "moderator", "Moderator"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.REGISTERED)

    # Only these roles may set expert_reviewed/verified (see docs/CLINICAL_GOVERNANCE.md).
    CLINICAL_APPROVER_ROLES = frozenset({Role.VET_REVIEWER, Role.ADMIN})

    @property
    def can_approve_clinical(self) -> bool:
        return self.is_superuser or self.role in self.CLINICAL_APPROVER_ROLES


class TotpDevice(models.Model):
    """An authenticator-app secret for one user. Unconfirmed until the first code is proven."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="totp_device")
    secret = models.CharField(max_length=200, help_text="Encrypted; see apps/accounts/mfa.py")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_step = models.BigIntegerField(default=0, help_text="Newest accepted 30 s time step")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TOTP for {self.user_id} ({'on' if self.confirmed_at else 'pending'})"


class RecoveryCode(models.Model):
    """A single-use fallback code, stored only as a keyed hash."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=64, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"recovery code for {self.user_id} ({'used' if self.used_at else 'unused'})"
