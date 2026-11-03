from django.conf import settings
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


class SourceKind(models.TextChoices):
    REGULATOR_LIST = "regulator_list", "Regulator product list"
    OPEN_DATA = "open_data", "Open data portal / API"
    DOCUMENT = "document", "Published document (PDF)"
    PORTAL = "portal", "Search portal"


class DataSource(TimeStampedModel):
    """An external data publisher we watch, and optionally import from.

    Two separate switches. `enabled` only lets the scheduled check read the public URL (robots.txt
    honoured) to see whether it is reachable and has changed; it never touches the catalogue.
    Importing needs an importer, `import_enabled`, and a person who has confirmed the publisher's
    terms (`terms_confirmed_at`). Imported records always start unreviewed (never public).
    """

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=160)
    publisher = models.CharField(max_length=160, blank=True)
    country_iso2 = models.CharField(max_length=2, blank=True, help_text="ISO 3166 alpha-2, if any")
    kind = models.CharField(max_length=16, choices=SourceKind.choices)
    landing_url = models.URLField(max_length=500, help_text="Human-readable page for the data")
    data_url = models.URLField(
        max_length=500, blank=True, help_text="Direct file/API URL to check and import"
    )
    licence_note = models.CharField(
        max_length=300, help_text="Licence as stated by the publisher (verify on their site)"
    )
    notes = models.TextField(blank=True)

    importer = models.CharField(
        max_length=24, blank=True, help_text="Adapter key; empty = monitor only"
    )
    enabled = models.BooleanField(default=True, help_text="Run the scheduled reachability check")
    import_enabled = models.BooleanField(default=False)
    check_interval_hours = models.PositiveSmallIntegerField(default=24)
    terms_confirmed_at = models.DateTimeField(null=True, blank=True, editable=False)
    terms_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    last_checked_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_ok = models.BooleanField(null=True, editable=False)
    last_http_status = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    last_error = models.CharField(max_length=300, blank=True, editable=False)
    consecutive_failures = models.PositiveSmallIntegerField(default=0, editable=False)
    fingerprint = models.CharField(max_length=200, blank=True, editable=False)
    last_changed_at = models.DateTimeField(null=True, blank=True, editable=False)
    update_available = models.BooleanField(default=False, editable=False)
    imported_fingerprint = models.CharField(max_length=200, blank=True, editable=False)
    last_imported_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_import_result = models.CharField(max_length=300, blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def check_url(self) -> str:
        return self.data_url or self.landing_url

    def clean(self):
        if self.import_enabled and not self.importer:
            raise ValidationError("Choose an importer before enabling import.")
        if self.import_enabled and not self.terms_confirmed_at:
            raise ValidationError(
                "Confirm the publisher's terms (admin action) before enabling import."
            )
        if self.importer and not self.data_url:
            raise ValidationError("An importer needs a direct data URL.")
