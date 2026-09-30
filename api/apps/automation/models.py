from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel


class RunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    OK = "ok", "Completed"
    FAILED = "failed", "Failed"


class JobRun(TimeStampedModel):
    """One execution of an automation task, kept as a plain audit trail."""

    task = models.CharField(max_length=40, db_index=True)
    status = models.CharField(max_length=8, choices=RunStatus.choices, default=RunStatus.RUNNING)
    finished_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.task} #{self.pk} ({self.status})"


class SourceHealth(TimeStampedModel):
    """Result of the latest reachability check of a Source's URL."""

    source = models.OneToOneField("sources.Source", on_delete=models.CASCADE, related_name="health")
    checked_at = models.DateTimeField()
    ok = models.BooleanField()
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error = models.CharField(max_length=200, blank=True)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "source health"


class FeedKind(models.TextChoices):
    JOBS = "jobs", "Jobs"
    SCHOLARSHIPS = "scholarships", "Scholarships"


class Feed(TimeStampedModel):
    """A staff-registered RSS/Atom feed. Disabled by default; items only ever become pending
    listings for a moderator, never public ones."""

    name = models.CharField(max_length=120)
    url = models.URLField(max_length=1000, unique=True)
    kind = models.CharField(max_length=14, choices=FeedKind.choices)
    organization = models.CharField(
        max_length=200, help_text="Shown as the employer/provider of every item from this feed"
    )
    default_country = models.ForeignKey(
        "countries.Country", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    default_job_type = models.CharField(max_length=12, blank=True, help_text="Required for jobs")
    default_level = models.CharField(
        max_length=12, blank=True, help_text="Required for scholarships"
    )
    license_note = models.CharField(
        max_length=300,
        blank=True,
        help_text="Terms allowing reuse of the feed (required to enable)",
    )
    robots_confirmed_at = models.DateTimeField(
        null=True, blank=True, editable=False, help_text="Set only by a successful robots.txt check"
    )
    enabled = models.BooleanField(default=False)
    last_checksum = models.CharField(max_length=64, blank=True, editable=False)
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_result = models.CharField(max_length=300, blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.enabled and not self.license_note.strip():
            raise ValidationError("Record the feed's licence/terms before enabling it.")
        if self.enabled and self.kind == FeedKind.JOBS and not self.default_job_type:
            raise ValidationError("Choose a default job type for a jobs feed.")
        if self.enabled and self.kind == FeedKind.SCHOLARSHIPS and not self.default_level:
            raise ValidationError("Choose a default level for a scholarships feed.")
