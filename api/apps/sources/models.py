from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import TimeStampedModel


class SourceType(models.TextChoices):
    REGULATORY = "regulatory", "Regulatory authority"
    PRODUCT_LABEL = "product_label", "Registered product label"
    MANUFACTURER = "manufacturer", "Manufacturer documentation"
    PAPER = "paper", "Peer-reviewed paper"
    TEXTBOOK = "textbook", "Veterinary textbook"
    PHARMACOLOGY_REF = "pharmacology_ref", "Pharmacology reference"
    GOVERNMENT = "government", "Government publication"
    UNIVERSITY = "university", "University source"
    ORGANIZATION = "organization", "Recognized veterinary organization"
    OTHER = "other", "Other"


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "unverified", "Not yet verified"
    PROVENANCE_OK = "provenance_ok", "Provenance and licence verified"
    CONFLICT = "conflict", "Conflicting evidence"
    INVALID = "invalid", "Invalid"


class Source(TimeStampedModel):
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    title = models.CharField(max_length=500)
    publisher = models.CharField(max_length=300, blank=True)
    author = models.CharField(max_length=500, blank=True)
    url = models.URLField(max_length=1000, blank=True)
    doi = models.CharField(max_length=200, blank=True)
    country = models.ForeignKey(
        "countries.Country", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    publication_date = models.DateField(null=True, blank=True)
    accessed_date = models.DateField(null=True, blank=True)
    edition = models.CharField(max_length=100, blank=True)
    license_note = models.CharField(max_length=300, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    license_url = models.URLField(max_length=500, blank=True)

    # Registry identity and automatic validation (apps.sources.linking). `canonical_url` is what
    # two entries are compared by, so the same page is never registered twice.
    canonical_url = models.CharField(max_length=1000, blank=True, db_index=True, editable=False)
    provider = models.CharField(max_length=60, blank=True, db_index=True)
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        db_index=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verification_note = models.CharField(max_length=300, blank=True, editable=False)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(url="") | ~models.Q(doi="") | ~models.Q(publisher=""),
                name="source_has_locator",
            )
        ]

    def __str__(self):
        return self.title[:80]

    def save(self, *args, **kwargs):
        from .urlutil import canonicalize_url

        self.canonical_url = canonicalize_url(self.url)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = {*kwargs["update_fields"], "canonical_url"}
        super().save(*args, **kwargs)


class SourceLink(models.Model):
    """Links any clinical or catalogue row to the Source that supports it."""

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="links")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    locator = models.CharField(max_length=200, blank=True, help_text="Page, section or table")

    class Meta:
        indexes = [models.Index(fields=["content_type", "object_id"])]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "content_type", "object_id", "locator"], name="uniq_source_link"
            )
        ]

    def __str__(self):
        return f"{self.source_id} -> {self.content_type_id}:{self.object_id}"


def sources_for(obj):
    """All Sources supporting `obj`."""
    ct = ContentType.objects.get_for_model(obj)
    return Source.objects.filter(links__content_type=ct, links__object_id=obj.pk).distinct()


def has_source(obj) -> bool:
    ct = ContentType.objects.get_for_model(obj)
    return SourceLink.objects.filter(content_type=ct, object_id=obj.pk).exists()


def has_usable_source(obj) -> bool:
    """A linked Source that has not been judged invalid. A raw URL on the record never counts."""
    ct = ContentType.objects.get_for_model(obj)
    return (
        SourceLink.objects.filter(content_type=ct, object_id=obj.pk)
        .exclude(source__verification_status=VerificationStatus.INVALID)
        .exists()
    )
