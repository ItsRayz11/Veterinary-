from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Append-only record of who changed what. Rows are never updated or deleted by the app."""

    at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=128)
    object_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["object_type", "object_id"])]
        ordering = ["-at"]

    def __str__(self):
        return f"{self.action} {self.object_type}:{self.object_id}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AuditLog entries are immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog entries cannot be deleted")


class ReviewStatus(models.TextChoices):
    """Verification states, see docs/CLINICAL_GOVERNANCE.md."""

    COMMUNITY_SUBMITTED = "community_submitted", "Community submitted"
    NEEDS_VERIFICATION = "needs_verification", "Needs verification"
    PENDING_REVIEW = "source_found_pending_review", "Source found, pending review"
    MANUFACTURER_SUPPLIED = "manufacturer_supplied", "Manufacturer supplied"
    OFFICIAL_REGULATORY = "official_regulatory", "Official regulatory source"
    EXPERT_REVIEWED = "expert_reviewed", "Expert reviewed"
    VERIFIED = "verified", "Verified"
    DEPRECATED = "deprecated", "Deprecated"
    ARCHIVED = "archived", "Archived"


PUBLIC_STATUSES = frozenset(
    {
        ReviewStatus.MANUFACTURER_SUPPLIED,
        ReviewStatus.OFFICIAL_REGULATORY,
        ReviewStatus.EXPERT_REVIEWED,
        ReviewStatus.VERIFIED,
    }
)
# Statuses that imply a qualified human signed off; development/seed data may never hold them.
SIGNED_OFF_STATUSES = (ReviewStatus.EXPERT_REVIEWED, ReviewStatus.VERIFIED)


class PublishableQuerySet(models.QuerySet):
    def public(self):
        """Publicly visible rows; dev/seed rows only when SHOW_DEVELOPMENT_DATA is on."""
        q = models.Q(review_status__in=[s.value for s in PUBLIC_STATUSES])
        if getattr(settings, "SHOW_DEVELOPMENT_DATA", False):
            q |= models.Q(is_development_data=True)
        return self.filter(q)


class PublishableModel(TimeStampedModel):
    """Mixin for anything shown publicly. Default is hidden until reviewed."""

    review_status = models.CharField(
        max_length=32,
        choices=ReviewStatus.choices,
        default=ReviewStatus.NEEDS_VERIFICATION,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    is_development_data = models.BooleanField(
        default=False, help_text="Seed/test record. Never shown as verified."
    )

    objects = PublishableQuerySet.as_manager()

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=~(
                    models.Q(is_development_data=True)
                    & models.Q(review_status__in=[s.value for s in SIGNED_OFF_STATUSES])
                ),
                name="%(app_label)s_%(class)s_no_signoff_on_dev_data",
            )
        ]

    @property
    def is_public(self) -> bool:
        if self.is_development_data and getattr(settings, "SHOW_DEVELOPMENT_DATA", False):
            return True
        return self.review_status in PUBLIC_STATUSES
