from django.db import models

from apps.core.models import PublishableModel
from apps.core.text import normalize_name, unique_slug


class University(PublishableModel):
    """A veterinary school, faculty or university. Imported records carry their source and are
    shown labelled as unreviewed until an editor signs them off (docs/CLINICAL_GOVERNANCE.md)."""

    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, editable=False)
    slug = models.SlugField(unique=True, editable=False)
    country = models.ForeignKey(
        "countries.Country", on_delete=models.PROTECT, related_name="universities"
    )
    city = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)
    summary = models.TextField(blank=True, help_text="Short description, with its source below")
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Provenance of the record and of its text.
    wikidata_id = models.CharField(max_length=20, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    source_license = models.CharField(max_length=80, blank=True)

    # One openly licensed image (logo or building photo) with the credit its licence requires.
    image_url = models.URLField(max_length=600, blank=True)
    image_page_url = models.URLField(max_length=600, blank=True)
    image_credit = models.CharField(max_length=300, blank=True)
    image_license = models.CharField(max_length=80, blank=True)
    image_license_url = models.URLField(max_length=300, blank=True)

    lists_unverified_imports = True

    class Meta(PublishableModel.Meta):
        ordering = ["name"]
        verbose_name_plural = "universities"
        constraints = [
            *PublishableModel.Meta.constraints,
            models.UniqueConstraint(
                fields=["country", "normalized_name"], name="uniq_university_country_name"
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_name(self.name)
        if not self.slug:
            self.slug = unique_slug(University, self.name, self)
        super().save(*args, **kwargs)
