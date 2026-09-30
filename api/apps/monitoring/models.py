from django.db import models
from django.utils import timezone


class ClientError(models.Model):
    """A browser-side error, deduplicated by fingerprint. No user, cookie or query data is kept."""

    fingerprint = models.CharField(max_length=64, unique=True)
    message = models.CharField(max_length=500)
    stack = models.TextField(blank=True)
    path = models.CharField(max_length=300, blank=True, help_text="Page path without query string")
    user_agent = models.CharField(max_length=200, blank=True)
    release = models.CharField(max_length=60, blank=True)
    count = models.PositiveIntegerField(default=1)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self):
        return f"{self.message[:60]} (x{self.count})"
