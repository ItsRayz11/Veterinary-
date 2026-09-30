from django.db import models

from apps.core.models import PublishableModel
from apps.core.text import normalize_name, unique_slug


class Company(PublishableModel):
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, editable=False)
    slug = models.SlugField(unique=True, editable=False)
    country = models.ForeignKey(
        "countries.Country", on_delete=models.PROTECT, related_name="companies"
    )
    is_manufacturer = models.BooleanField(default=False)
    is_importer = models.BooleanField(default=False)
    is_distributor = models.BooleanField(default=False)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_verified_profile = models.BooleanField(default=False)

    lists_unverified_imports = True

    class Meta(PublishableModel.Meta):
        ordering = ["name"]
        constraints = [
            *PublishableModel.Meta.constraints,
            models.UniqueConstraint(
                fields=["country", "normalized_name"], name="uniq_company_country_name"
            ),
        ]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_name(self.name)
        if not self.slug:
            self.slug = unique_slug(Company, self.name, self)
        super().save(*args, **kwargs)


class CompanyAlias(models.Model):
    """Alternate spellings/abbreviations, used by entity matching and search."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="aliases")
    alias = models.CharField(max_length=200)
    normalized_alias = models.CharField(max_length=200, editable=False, unique=True)

    def __str__(self):
        return self.alias

    def save(self, *args, **kwargs):
        self.normalized_alias = normalize_name(self.alias)
        super().save(*args, **kwargs)
