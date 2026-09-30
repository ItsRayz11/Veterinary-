from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

DEFAULT_LIFETIME_DAYS = 90


class ListingStatus(models.TextChoices):
    PENDING = "pending", "Pending moderation"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class ListingQuerySet(models.QuerySet):
    def public(self):
        """Approved and not yet expired. Expired listings disappear without any cleanup job."""
        return self.filter(status=ListingStatus.APPROVED, expires_on__gte=timezone.localdate())


class Listing(TimeStampedModel):
    """Common fields of a moderated opportunity. Nothing is public until a moderator approves."""

    title = models.CharField(max_length=200)
    organization = models.CharField(max_length=200)
    country = models.ForeignKey(
        "countries.Country", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    description = models.TextField(max_length=3000)
    apply_url = models.URLField(max_length=1000, help_text="Where to apply (the original posting)")
    closes_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Set on approval: the closing date, or 90 days after approval if none.",
    )
    status = models.CharField(
        max_length=10, choices=ListingStatus.choices, default=ListingStatus.PENDING, db_index=True
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.CharField(max_length=300, blank=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.organization})"

    @staticmethod
    def default_expiry(closes_on, today):
        return closes_on or today + timedelta(days=DEFAULT_LIFETIME_DAYS)


class JobType(models.TextChoices):
    FULL_TIME = "full_time", "Full time"
    PART_TIME = "part_time", "Part time"
    CONTRACT = "contract", "Contract"
    INTERNSHIP = "internship", "Internship"
    VOLUNTEER = "volunteer", "Volunteer"


class Job(Listing):
    city = models.CharField(max_length=100, blank=True)
    job_type = models.CharField(max_length=12, choices=JobType.choices)

    class Meta(Listing.Meta):
        indexes = [models.Index(fields=["status", "expires_on"])]


class ScholarshipLevel(models.TextChoices):
    DVM = "dvm", "DVM / BVSc"
    MASTERS = "masters", "Masters"
    PHD = "phd", "PhD"
    POSTDOC = "postdoc", "Postdoctoral"
    SHORT_COURSE = "short_course", "Short course / training"
    OTHER = "other", "Other"


class Funding(models.TextChoices):
    FULL = "full", "Fully funded"
    PARTIAL = "partial", "Partially funded"
    UNKNOWN = "unknown", "Not stated"


class Scholarship(Listing):
    level = models.CharField(max_length=12, choices=ScholarshipLevel.choices)
    funding = models.CharField(max_length=8, choices=Funding.choices, default=Funding.UNKNOWN)

    class Meta(Listing.Meta):
        indexes = [models.Index(fields=["status", "expires_on"])]


class ListingReport(TimeStampedModel):
    """A user flagging a live listing (scam, expired, wrong). One report per user per listing."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    listing = GenericForeignKey("content_type", "object_id")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    message = models.CharField(max_length=300)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "reporter"], name="uniq_report_per_user"
            )
        ]
