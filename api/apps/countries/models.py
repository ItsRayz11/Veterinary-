from django.db import models

from apps.core.models import TimeStampedModel


class Country(TimeStampedModel):
    """Jurisdiction. Behaviour differences live in data, never in country-code branches."""

    iso2 = models.CharField(max_length=2, unique=True)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    currency_code = models.CharField(max_length=3, help_text="ISO 4217")
    regulator_name = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True, help_text="Shown in country pickers")
    sort_order = models.PositiveSmallIntegerField(default=100)

    class IndexMode(models.TextChoices):
        AUTO = "auto", "Automatic (coverage thresholds)"
        NEVER = "never", "Never index"
        ALWAYS = "always", "Always index (owner override)"

    index_mode = models.CharField(max_length=8, choices=IndexMode.choices, default=IndexMode.AUTO)
    index_min_registrations = models.PositiveIntegerField(
        default=300,
        help_text="Public registrations needed before search engines may index this country",
    )
    index_min_provenance_pct = models.PositiveSmallIntegerField(
        default=95,
        help_text="% of public registrations that must carry a feed source and a last-checked date",
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name
