from django.conf import settings
from django.db import models
from django.utils import timezone


class PushSubscription(models.Model):
    """One browser/device a signed-in user agreed to be notified on. Removed when it expires."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user_id}: {self.endpoint[:40]}"
