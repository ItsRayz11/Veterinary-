from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class AnswerStatus(models.TextChoices):
    ANSWERED = "answered", "Answered from reviewed records"
    NO_DATA = "no_reviewed_data", "No reviewed records matched"
    UNVERIFIED = "unverified", "Answer failed verification (not shown)"
    UNAVAILABLE = "unavailable", "Assistant not configured"
    ERROR = "error", "Model call failed"


class AssistantLog(TimeStampedModel):
    """Every question and outcome, kept so staff can audit what the assistant said and why."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assistant_logs"
    )
    question = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=AnswerStatus.choices)
    answer = models.TextField(blank=True)
    citations = models.JSONField(default=list, blank=True)
    retrieved = models.JSONField(
        default=list, blank=True, help_text="Generic slugs given as context"
    )
    model = models.CharField(max_length=60, blank=True)
    detail = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
