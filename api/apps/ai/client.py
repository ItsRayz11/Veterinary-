"""Server-side OpenAI-compatible chat client with budget, rate limit and fallback.

Keys are read from the environment at call time and never stored, logged or returned. Prompts are
not stored. Callers must pass only data that may leave the platform (no user contact details, no
private submissions); `minimise` strips obvious identifiers as a backstop.
"""

import json
import os
import re
import urllib.error
import urllib.request
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from apps.automation import safe_http

from .models import AIProvider, AITaskRoute, AIUsage

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
# Planning rate (USD per 1M tokens) used only for budget ESTIMATES. Real provider prices differ
# and are not invented here; compare with the provider invoice.
ESTIMATE_PER_MILLION = Decimal("10")


class AIError(Exception):
    """Safe-to-show failure (no secrets)."""


def minimise(text: str) -> str:
    return PHONE.sub("[phone]", EMAIL.sub("[email]", text))[:8000]


def month_spend(provider: AIProvider) -> Decimal:
    start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = provider.usage.filter(at__gte=start).aggregate(t=Sum("cost_usd"))["t"]
    return total or Decimal("0")


def _key(provider: AIProvider) -> str:
    key = os.environ.get(provider.api_key_env, "")
    if not key:
        raise AIError(f"The server has no key set for {provider}.")
    return key


def _rate_ok(provider: AIProvider) -> bool:
    k = f"ai-rate-{provider.pk}-{timezone.now():%Y%m%d%H%M}"
    cache.add(k, 0, 120)
    return cache.incr(k) <= provider.rate_limit_per_minute


def _call(provider: AIProvider, model: str, messages: list[dict], max_tokens: int) -> dict:
    if not provider.enabled:
        raise AIError(f"{provider} is disabled.")
    if provider.monthly_budget_usd <= month_spend(provider):
        raise AIError(f"{provider} has reached its monthly budget.")
    if not _rate_ok(provider):
        raise AIError(f"{provider} rate limit reached; try again shortly.")
    url = provider.base_url.rstrip("/") + "/chat/completions"
    try:
        safe_http.assert_public_url(url)
    except safe_http.FetchError as exc:
        raise AIError(str(exc)) from exc
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(  # noqa: S310 - https and public address checked above
        url,
        data=body,
        headers={"Authorization": f"Bearer {_key(provider)}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=provider.timeout_seconds) as resp:  # noqa: S310
            return json.loads(resp.read(2_000_000))
    except urllib.error.HTTPError as exc:
        raise AIError(f"Provider returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise AIError(f"Provider unreachable or invalid response ({type(exc).__name__}).") from exc


def _record(provider, model, task, actor, data=None, error=""):
    usage = (data or {}).get("usage") or {}
    p, c = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    cost = (Decimal(p + c) / Decimal(1_000_000) * ESTIMATE_PER_MILLION).quantize(Decimal("0.00001"))
    AIUsage.objects.create(
        provider=provider, model=model, task=task, actor=actor, prompt_tokens=p,
        completion_tokens=c, cost_usd=cost, ok=not error, error=error[:200],
    )  # fmt: skip


def run_task(task: str, prompt: str, *, system: str = "", actor=None) -> str:
    """Route a task to its provider, falling back once within budget. Returns the text."""
    route = (
        AITaskRoute.objects.filter(task=task, enabled=True)
        .select_related("provider", "fallback_provider")
        .first()
    )
    if route is None:
        raise AIError("No provider is configured for this task.")
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": minimise(prompt)}
    ]
    attempts = [(route.provider, route.model)]
    if route.fallback_provider_id:
        attempts.append((route.fallback_provider, route.fallback_model or route.model))
    last = "No attempt made."
    for provider, model in attempts:
        try:
            data = _call(provider, model, messages, route.max_tokens)
            text = str(data["choices"][0]["message"]["content"])
        except (AIError, KeyError, IndexError, TypeError) as exc:
            last = str(exc) if isinstance(exc, AIError) else "Malformed provider response."
            _record(provider, model, task, actor, error=last)
            continue
        _record(provider, model, task, actor, data)
        return text
    raise AIError(last)


def check_connection(provider: AIProvider) -> tuple[bool, str]:
    """Authenticated call to the models endpoint; never sends user data."""
    try:
        if not provider.enabled:
            raise AIError("Enable the provider first.")
        url = provider.base_url.rstrip("/") + "/models"
        safe_http.assert_public_url(url)
        req = urllib.request.Request(  # noqa: S310
            url, headers={"Authorization": f"Bearer {_key(provider)}"}
        )
        with urllib.request.urlopen(req, timeout=provider.timeout_seconds) as resp:  # noqa: S310
            json.loads(resp.read(2_000_000))
        ok, msg = True, "Connected."
    except (AIError, safe_http.FetchError) as exc:
        ok, msg = False, str(exc)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 405) and provider.default_model:
            # Some gateways (e.g. AgentRouter) do not document /models: try one tiny completion.
            try:
                data = _call(
                    provider, provider.default_model, [{"role": "user", "content": "ping"}], 1
                )
                _record(provider, provider.default_model, "conn-test", None, data)
                ok, msg = True, "Connected (models list not available; a 1-token call worked)."
            except AIError as inner:
                ok, msg = False, str(inner)
        elif exc.code in (404, 405):
            ok, msg = (
                False,
                "No /models endpoint; set a preferred model so a 1-token call can test it.",
            )
        else:
            ok, msg = False, f"HTTP {exc.code} from provider."
    except Exception as exc:  # noqa: BLE001
        ok, msg = False, f"Could not connect ({type(exc).__name__})."
    provider.last_test_at, provider.last_test_ok = timezone.now(), ok
    provider.last_test_message = msg[:200]
    provider.save(update_fields=["last_test_at", "last_test_ok", "last_test_message", "updated_at"])
    return ok, msg
