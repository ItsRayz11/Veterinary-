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

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name
