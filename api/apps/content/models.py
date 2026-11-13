import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.text import unique_slug

TAG = re.compile(r"<[^>]*>?")
HTTPS = re.compile(r"https://[^\s)]+")


def strip_markup(text: str) -> str:
    """Articles are plain text with a tiny markdown subset. Any HTML is removed, never rendered."""
    return TAG.sub("", text or "")


class ArticleStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    REVIEW = "review", "In review"
    SCHEDULED = "scheduled", "Scheduled"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"


class ArticleQuerySet(models.QuerySet):
    def public(self):
        now = timezone.now()
        return self.filter(
            status__in=[ArticleStatus.PUBLISHED, ArticleStatus.SCHEDULED],
            publish_at__lte=now,
            reviewed_by__isnull=False,
        )


class Article(TimeStampedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, editable=False)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField(help_text="Plain text; # headings, - lists, [text](https://url) links")
    category = models.CharField(max_length=60, blank=True)
    tags = models.CharField(max_length=200, blank=True, help_text="Comma separated")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="articles"
    )
    author_credit = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=10, choices=ArticleStatus.choices, default=ArticleStatus.DRAFT, db_index=True
    )
    publish_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=170, blank=True)
    canonical_url = models.URLField(blank=True)
    ai_assisted = models.BooleanField(default=False)
    medical = models.BooleanField(
        default=False, help_text="Clinical content: only a veterinarian reviewer/admin may publish"
    )
    references = models.TextField(blank=True, help_text="One https URL per line")
    reject_reason = models.CharField(max_length=300, blank=True)
    revision = models.PositiveIntegerField(default=1, editable=False)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-publish_at"])]

    def __str__(self):
        return self.title

    def clean(self):
        self.title = strip_markup(self.title).strip()
        self.excerpt = strip_markup(self.excerpt)
        self.body = strip_markup(self.body)
        self.meta_title = strip_markup(self.meta_title)
        self.meta_description = strip_markup(self.meta_description)
        if not self.title:
            raise ValidationError("A title is required.")
        if self.canonical_url and not self.canonical_url.startswith("https://"):
            raise ValidationError("Canonical URL must use https.")
        bad = [u for u in self.reference_list if not u.startswith("https://")]
        if bad:
            raise ValidationError("References must be https URLs, one per line.")
        if len(self.body) > 60_000:
            raise ValidationError("The article is too long.")

    @property
    def reference_list(self) -> list[str]:
        return [ln.strip() for ln in self.references.splitlines() if ln.strip()]

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def outbound_links(self) -> list[str]:
        found = set(HTTPS.findall(self.body)) | set(self.reference_list)
        return sorted(found)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Article, self.title, self)
        super().save(*args, **kwargs)


class ArticleRevision(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    body = models.TextField()
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        unique_together = [("article", "number")]

    def __str__(self):
        return f"{self.article_id} r{self.number}"


class TopicBasis(models.TextChoices):
    CATALOGUE_GAP = "catalogue_gap", "Gap found in VetRef data (checkable)"
    MODEL = "model_suggestion", "General AI suggestion (not trend data)"
    VERIFIED_TREND = "verified_trend", "From a registered trend source"


class TopicStatus(models.TextChoices):
    NEW = "new", "New"
    ACCEPTED = "accepted", "Accepted"
    DISMISSED = "dismissed", "Dismissed"


class TopicSuggestion(TimeStampedModel):
    title = models.CharField(max_length=200)
    rationale = models.CharField(max_length=400)
    basis = models.CharField(max_length=20, choices=TopicBasis.choices)
    evidence_url = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=TopicStatus.choices, default=TopicStatus.NEW)
    outline = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
