from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import (
    PublishableModel,
    PublishableQuerySet,
    ReviewStatus,
    TimeStampedModel,
)
from apps.core.text import unique_slug
from apps.units.models import Dimension


class Indication(TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Indication, self.name, self)
        super().save(*args, **kwargs)


class Route(models.Model):
    code = models.CharField(max_length=16, unique=True, help_text="IM, IV, SC, PO, ...")
    name = models.CharField(max_length=64)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Commodity(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=64)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "commodities"

    def __str__(self):
        return self.name


class ClinicalRecord(PublishableModel):
    """Base for clinical data: a submitter, a different reviewer, and at least one source."""

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta(PublishableModel.Meta):
        abstract = True


# Statuses whose doses may feed the calculator or be shown as a dose recommendation.
CALCULATOR_STATUSES = frozenset(
    {ReviewStatus.VERIFIED, ReviewStatus.EXPERT_REVIEWED, ReviewStatus.OFFICIAL_REGULATORY}
)


class DoseQuerySet(PublishableQuerySet):
    def calculator_ready(self):
        return self.filter(review_status__in=[s.value for s in CALCULATOR_STATUSES])


class DoseRegimen(ClinicalRecord):
    """One structured dose: generic (optionally product-specific) x species x indication x route."""

    generic = models.ForeignKey(
        "pharma.Generic", on_delete=models.PROTECT, related_name="dose_regimens"
    )
    product = models.ForeignKey(
        "pharma.Product",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="dose_regimens",
        help_text="Set when the dose comes from that product's label.",
    )
    species = models.ForeignKey("species.Species", on_delete=models.PROTECT, related_name="+")
    indication = models.ForeignKey(
        Indication, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="+")
    country = models.ForeignKey(
        "countries.Country",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Empty = general reference dose, not tied to one jurisdiction.",
    )
    dose_min = models.DecimalField(max_digits=12, decimal_places=4)
    dose_max = models.DecimalField(max_digits=12, decimal_places=4)
    dose_unit = models.ForeignKey(
        "units.Unit", on_delete=models.PROTECT, related_name="+", help_text="A dose-rate unit"
    )
    interval_hours = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, help_text="Hours between doses"
    )
    duration_min_days = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_max_days = models.PositiveSmallIntegerField(null=True, blank=True)
    max_single_dose = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    max_single_dose_unit = models.ForeignKey(
        "units.Unit", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    notes = models.TextField(blank=True)

    objects = DoseQuerySet.as_manager()
    history = HistoricalRecords()

    class Meta(ClinicalRecord.Meta):
        constraints = [
            *ClinicalRecord.Meta.constraints,
            models.CheckConstraint(condition=models.Q(dose_min__gt=0), name="dose_min_positive"),
            models.CheckConstraint(
                condition=models.Q(dose_max__gte=models.F("dose_min")), name="dose_max_gte_min"
            ),
            models.CheckConstraint(
                condition=models.Q(interval_hours__isnull=True) | models.Q(interval_hours__gt=0),
                name="interval_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(duration_min_days__isnull=True)
                | models.Q(duration_max_days__isnull=True)
                | models.Q(duration_max_days__gte=models.F("duration_min_days")),
                name="duration_max_gte_min",
            ),
            models.CheckConstraint(
                condition=models.Q(max_single_dose__isnull=True)
                | models.Q(max_single_dose_unit__isnull=False),
                name="max_dose_has_unit",
            ),
        ]

    def __str__(self):
        return f"{self.generic} / {self.species} / {self.route}: {self.dose_min}-{self.dose_max}"

    @property
    def is_calculator_ready(self) -> bool:
        return self.review_status in CALCULATOR_STATUSES

    def clean(self):
        if self.dose_unit_id and self.dose_unit.dimension != Dimension.DOSE_RATE:
            raise ValidationError({"dose_unit": "Dose unit must be a dose-rate unit (e.g. mg/kg)."})
        if self.product_id and self.product.generic_id != self.generic_id:
            raise ValidationError({"product": "Product does not belong to this generic."})


class WithdrawalQuerySet(PublishableQuerySet):
    # Stricter than other clinical data: only regulator- or vet-verified values may be shown.
    def public(self):
        return self.filter(
            review_status__in=[ReviewStatus.OFFICIAL_REGULATORY.value, ReviewStatus.VERIFIED.value]
        )


class TimeUnit(models.TextChoices):
    HOURS = "hours", "Hours"
    DAYS = "days", "Days"


class WithdrawalPeriod(ClinicalRecord):
    """Withdrawal per product x country x species x commodity x route (never per generic)."""

    product = models.ForeignKey(
        "pharma.Product", on_delete=models.PROTECT, related_name="withdrawal_periods"
    )
    country = models.ForeignKey("countries.Country", on_delete=models.PROTECT, related_name="+")
    species = models.ForeignKey("species.Species", on_delete=models.PROTECT, related_name="+")
    commodity = models.ForeignKey(Commodity, on_delete=models.PROTECT, related_name="+")
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="+")
    duration_value = models.DecimalField(max_digits=8, decimal_places=2)
    duration_unit = models.CharField(max_length=8, choices=TimeUnit.choices)
    regimen_note = models.CharField(max_length=300, blank=True)
    regulatory_status = models.CharField(max_length=200, blank=True)

    objects = WithdrawalQuerySet.as_manager()
    history = HistoricalRecords()

    class Meta(ClinicalRecord.Meta):
        constraints = [
            *ClinicalRecord.Meta.constraints,
            models.UniqueConstraint(
                fields=["product", "country", "species", "commodity", "route"],
                name="uniq_withdrawal_context",
            ),
            models.CheckConstraint(
                condition=models.Q(duration_value__gte=0), name="withdrawal_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.product} {self.species}/{self.commodity}: {self.duration_hours}h"

    @property
    def duration_hours(self) -> Decimal:
        factor = Decimal(24) if self.duration_unit == TimeUnit.DAYS else Decimal(1)
        return self.duration_value * factor


class NoteKind(models.TextChoices):
    CONTRAINDICATION = "contraindication", "Contraindication"
    PRECAUTION = "precaution", "Precaution"
    ADVERSE_EFFECT = "adverse_effect", "Adverse effect"
    TOXICITY = "toxicity", "Toxicity"
    WARNING = "warning", "Warning"


class ClinicalNote(ClinicalRecord):
    """A short, individually-sourced safety statement about a generic (optionally per species)."""

    generic = models.ForeignKey(
        "pharma.Generic", on_delete=models.PROTECT, related_name="clinical_notes"
    )
    species = models.ForeignKey(
        "species.Species", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    kind = models.CharField(max_length=20, choices=NoteKind.choices)
    text = models.TextField()

    history = HistoricalRecords()

    class Meta(ClinicalRecord.Meta):
        indexes = [models.Index(fields=["generic", "kind"])]

    def __str__(self):
        return f"{self.generic} {self.kind}: {self.text[:40]}"


class Severity(models.TextChoices):
    CONTRAINDICATED = "contraindicated", "Contraindicated"
    MAJOR = "major", "Major"
    MODERATE = "moderate", "Moderate"
    MINOR = "minor", "Minor"


class Interaction(ClinicalRecord):
    """Interaction between two generics. Stored once as an ordered pair (a.id < b.id)."""

    generic_a = models.ForeignKey("pharma.Generic", on_delete=models.PROTECT, related_name="+")
    generic_b = models.ForeignKey("pharma.Generic", on_delete=models.PROTECT, related_name="+")
    severity = models.CharField(max_length=16, choices=Severity.choices)
    description = models.TextField()

    history = HistoricalRecords()

    class Meta(ClinicalRecord.Meta):
        constraints = [
            *ClinicalRecord.Meta.constraints,
            models.CheckConstraint(
                condition=models.Q(generic_a__lt=models.F("generic_b")), name="interaction_ordered"
            ),
            models.UniqueConstraint(fields=["generic_a", "generic_b"], name="uniq_interaction"),
        ]

    def __str__(self):
        return f"{self.generic_a} + {self.generic_b} ({self.severity})"

    @classmethod
    def create_pair(cls, a, b, **kwargs):
        if a.pk == b.pk:
            raise ValueError("An interaction needs two different generics")
        lo, hi = (a, b) if a.pk < b.pk else (b, a)
        return cls.objects.create(generic_a=lo, generic_b=hi, **kwargs)
