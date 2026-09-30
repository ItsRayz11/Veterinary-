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
