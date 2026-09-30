from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class PriceType(models.TextChoices):
    MANUFACTURER_SUGGESTED = "manufacturer_suggested", "Manufacturer suggested price"
    DISTRIBUTOR = "distributor", "Distributor price"
    RETAIL = "retail", "Retail price"


class PriceOrigin(models.TextChoices):
    OFFICIAL = "official", "Official/regulatory source"
    MANUFACTURER = "manufacturer", "Manufacturer supplied"
    EDITORIAL = "editorial", "Entered by editors from a cited source"
    USER_SUBMITTED = "user_submitted", "User submitted (moderated)"


class PriceQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class PriceRecord(TimeStampedModel):
    """One observed price for a pack. Append-only: a new price is a new row, never an edit."""

    pack = models.ForeignKey("pharma.ProductPack", on_delete=models.PROTECT, related_name="prices")
    country = models.ForeignKey("countries.Country", on_delete=models.PROTECT, related_name="+")
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=3, help_text="ISO 4217")
    price_type = models.CharField(max_length=24, choices=PriceType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    origin = models.CharField(max_length=16, choices=PriceOrigin.choices)
    source = models.ForeignKey(
        "sources.Source", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    observed_on = models.DateField(help_text="Date the price applied or was checked")
    verified_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    confidence = models.DecimalField(max_digits=3, decimal_places=2, default=1)
    is_published = models.BooleanField(default=False, db_index=True)

    objects = PriceQuerySet.as_manager()

    class Meta:
        ordering = ["-observed_on", "-id"]
        indexes = [models.Index(fields=["pack", "country", "price_type", "-observed_on"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="price_positive"),
            models.CheckConstraint(
                condition=models.Q(confidence__gte=0) & models.Q(confidence__lte=1),
                name="price_confidence_0_1",
            ),
            # Non-user prices must cite where they came from.
            models.CheckConstraint(
                condition=models.Q(origin="user_submitted") | models.Q(source__isnull=False),
                name="price_needs_source_unless_user",
            ),
        ]

    def __str__(self):
        return f"{self.pack} {self.currency} {self.amount} ({self.observed_on})"

    def save(self, *args, **kwargs):
        if self.pk:
            # Only publication/verification flags may change; the observed price is immutable.
            allowed = {"is_published", "verified_at", "updated_at"}
            uf = kwargs.get("update_fields")
            if uf is None or not set(uf) <= allowed:
                raise ValueError("Price records are append-only; create a new record instead.")
        super().save(*args, **kwargs)


class SubmissionKind(models.TextChoices):
    NEW_PRICE = "new_price", "Updated price"
    REPORT_INCORRECT = "report_incorrect", "Report incorrect price"


class SubmissionStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class PriceSubmission(TimeStampedModel):
    """A public price suggestion or error report. Never shown until a moderator approves."""

    kind = models.CharField(max_length=16, choices=SubmissionKind.choices)
    pack = models.ForeignKey("pharma.ProductPack", on_delete=models.CASCADE, related_name="+")
    country = models.ForeignKey("countries.Country", on_delete=models.PROTECT, related_name="+")
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    price_type = models.CharField(max_length=24, choices=PriceType.choices, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target = models.ForeignKey(
        PriceRecord, null=True, blank=True, on_delete=models.SET_NULL, related_name="reports"
    )
    note = models.CharField(max_length=500, blank=True)
    evidence_url = models.URLField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="price_submissions"
    )
    status = models.CharField(
        max_length=10, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(kind="new_price")
                | (models.Q(amount__isnull=False, amount__gt=0) & ~models.Q(price_type="")),
                name="new_price_needs_amount_and_type",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="report_incorrect") | models.Q(target__isnull=False),
                name="report_needs_target",
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.pack_id} [{self.status}]"
