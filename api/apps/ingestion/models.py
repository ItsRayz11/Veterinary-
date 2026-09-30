from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class BatchStatus(models.TextChoices):
    STAGED = "staged", "Staged (awaiting review)"
    COMPLETED = "completed", "Completed"


class RowStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved into catalogue (unreviewed)"
    REJECTED = "rejected", "Rejected"
    DUPLICATE = "duplicate", "Duplicate of an existing record"
    ERROR = "error", "Invalid row"


class ImportBatch(TimeStampedModel):
    """One uploaded file. Provenance (source, checksum, licence) is fixed at staging time."""

    kind = models.CharField(max_length=24, default="products")
    country = models.ForeignKey(
        "countries.Country", on_delete=models.PROTECT, related_name="import_batches"
    )
    source = models.ForeignKey("sources.Source", on_delete=models.PROTECT, related_name="+")
    file_name = models.CharField(max_length=200, blank=True)
    checksum = models.CharField(max_length=64, help_text="SHA-256 of the raw file")
    status = models.CharField(
        max_length=12, choices=BatchStatus.choices, default=BatchStatus.STAGED
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "country", "checksum"], name="uniq_import_file_per_country"
            )
        ]

    def __str__(self):
        return f"{self.kind} import #{self.pk} ({self.file_name or 'pasted'})"


class StagedRecord(TimeStampedModel):
    """One parsed row. Never touches the catalogue until a staff member approves it."""

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    raw = models.JSONField()
    brand_name = models.CharField(max_length=200, blank=True)
    generic_name = models.CharField(max_length=200, blank=True)
    manufacturer_name = models.CharField(max_length=200, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    registration_status = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=12, choices=RowStatus.choices, default=RowStatus.PENDING)
    message = models.CharField(max_length=300, blank=True)
    matched_generic = models.ForeignKey(
        "pharma.Generic", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    matched_company = models.ForeignKey(
        "companies.Company", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    matched_product = models.ForeignKey(
        "pharma.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["batch", "row_number"]
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_number"], name="uniq_batch_row")
        ]

    def __str__(self):
        return f"{self.brand_name or '?'} / {self.generic_name or '?'} (row {self.row_number})"
