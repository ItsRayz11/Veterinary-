import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel

ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,63}")


class ProviderKind(models.TextChoices):
    OPENAI = "openai", "OpenAI API"
    OPENROUTER = "openrouter", "OpenRouter"
    AGENTROUTER = "agentrouter", "AgentRouter (OpenAI-compatible; verify its docs first)"


# Hosts a provider kind may call. AgentRouter has no fixed host here: the admin supplies an https
# base URL, which must still resolve to a public address (SSRF guard in the client).
FIXED_HOSTS = {ProviderKind.OPENAI: "api.openai.com", ProviderKind.OPENROUTER: "openrouter.ai"}


class AIProvider(TimeStampedModel):
    """A configured inference provider. The API key lives in the server environment only."""

    kind = models.CharField(max_length=12, choices=ProviderKind.choices, unique=True)
    enabled = models.BooleanField(default=False)
    base_url = models.URLField(max_length=300, help_text="OpenAI-compatible base, https only")
    api_key_env = models.CharField(
        max_length=64, help_text="NAME of the server environment variable holding the key"
    )
    default_model = models.CharField(max_length=120, blank=True)
    timeout_seconds = models.PositiveSmallIntegerField(default=20)
    rate_limit_per_minute = models.PositiveSmallIntegerField(default=30)
    monthly_budget_usd = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), help_text="0 = no spending allowed"
    )
    last_test_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_test_ok = models.BooleanField(null=True, editable=False)
    last_test_message = models.CharField(max_length=200, blank=True, editable=False)

    def __str__(self):
        return self.get_kind_display()

    def clean(self):
        if not ENV_NAME.fullmatch(self.api_key_env or ""):
            raise ValidationError("Key reference must be an environment variable NAME, not a key.")
        if not self.base_url.startswith("https://"):
            raise ValidationError("The base URL must use https.")
        fixed = FIXED_HOSTS.get(self.kind)
        if fixed and self.base_url.split("/")[2] != fixed:
            raise ValidationError(f"{self.get_kind_display()} must use {fixed}.")


class AITask(models.TextChoices):
    TAGGING = "tagging", "Tagging / deduplication hints"
    EXTRACTION = "extraction", "Structured extraction"
    DRAFTING = "drafting", "Editorial drafting"
    SUMMARISING = "summarising", "Summarising"
    TRANSLATION = "translation", "Translation"
    TRIAGE = "triage", "Report / question triage"
    SUGGESTIONS = "suggestions", "Topic suggestions"


class AITaskRoute(TimeStampedModel):
    """Which provider and model handle a task, and the fallback within the budget."""

    task = models.CharField(max_length=14, choices=AITask.choices, unique=True)
    provider = models.ForeignKey(AIProvider, on_delete=models.PROTECT, related_name="routes")
    model = models.CharField(max_length=120)
    fallback_provider = models.ForeignKey(
        AIProvider, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    fallback_model = models.CharField(max_length=120, blank=True)
    max_tokens = models.PositiveIntegerField(default=800)
    enabled = models.BooleanField(default=True)


class AIUsage(models.Model):
    """Append-only usage ledger: sizes and cost estimates only, never prompts or keys."""

    at = models.DateTimeField(auto_now_add=True, db_index=True)
    provider = models.ForeignKey(AIProvider, on_delete=models.PROTECT, related_name="usage")
    model = models.CharField(max_length=120)
    task = models.CharField(max_length=14)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=5, default=Decimal("0"))
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.task} via {self.model}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AIUsage entries are immutable")
        super().save(*args, **kwargs)
