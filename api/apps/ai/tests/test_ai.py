import json
from decimal import Decimal
from unittest import mock

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.ai import client
from apps.ai.models import AIProvider, AITaskRoute, AIUsage
from apps.ai.triage import triage_report
from apps.core.models import AuditLog


def api(role):
    u, _ = User.objects.get_or_create(username=f"u-{role}", defaults={"role": role})
    c = APIClient()
    c.force_login(u)
    return c


def make_provider(**kw):
    base = dict(
        kind="openai", enabled=True, base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY", monthly_budget_usd=Decimal("5"),
    )  # fmt: skip
    return AIProvider.objects.create(**{**base, **kw})


@pytest.mark.django_db
def test_only_admin_manages_providers_and_key_value_is_never_returned(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value")
    body = {
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    }
    assert (
        api(Role.EDITOR).post("/api/v1/staff/ai/providers/", body, format="json").status_code == 403
    )
    r = api(Role.ADMIN).post("/api/v1/staff/ai/providers/", body, format="json")
    assert r.status_code == 201
    assert r.json()["key_present"] is True
    assert "sk-super-secret-value" not in r.content.decode()
    listing = api(Role.ADMIN).get("/api/v1/staff/ai/providers/")
    assert "sk-super-secret-value" not in listing.content.decode()
    assert AuditLog.objects.filter(action="ai_provider_created").exists()


@pytest.mark.django_db
def test_rejects_key_in_reference_field_and_wrong_host():
    c = api(Role.ADMIN)
    bad_key = {
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "sk-abc123",
    }
    assert c.post("/api/v1/staff/ai/providers/", bad_key, format="json").status_code == 400
    wrong_host = {
        "kind": "openai",
        "base_url": "https://evil.example/v1",
        "api_key_env": "OPENAI_API_KEY",
    }
    assert c.post("/api/v1/staff/ai/providers/", wrong_host, format="json").status_code == 400
    http = {"kind": "agentrouter", "base_url": "http://x.example", "api_key_env": "AGENT_KEY"}
    assert c.post("/api/v1/staff/ai/providers/", http, format="json").status_code == 400


@pytest.mark.django_db
def test_run_task_records_usage_and_falls_back(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OR_KEY", "k2")
    a = make_provider()
    b = make_provider(
        kind="openrouter", base_url="https://openrouter.ai/api/v1", api_key_env="OR_KEY"
    )
    AITaskRoute.objects.create(
        task="tagging", provider=a, model="m1", fallback_provider=b, fallback_model="m2"
    )
    calls = []

    def fake(provider, model, messages, max_tokens):
        calls.append(provider.kind)
        if provider.kind == "openai":
            raise client.AIError("Provider returned HTTP 500.")
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    with mock.patch.object(client, "_call", fake):
        assert client.run_task("tagging", "hello a@b.com") == "ok"
    assert calls == ["openai", "openrouter"]
    assert (
        AIUsage.objects.filter(ok=False).count() == 1
        and AIUsage.objects.filter(ok=True).count() == 1
    )


@pytest.mark.django_db
def test_budget_zero_blocks_calls_and_prompts_are_minimised(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    p = make_provider(monthly_budget_usd=Decimal("0"))
    with pytest.raises(client.AIError, match="budget"):
        client._call(p, "m", [], 10)
    assert "[email]" in client.minimise("mail me at a.b@c.org") and "[phone]" in client.minimise(
        "call +44 20 7946 0958"
    )
    assert json  # json import used by provider payloads


@pytest.mark.django_db
def test_no_route_raises():
    with pytest.raises(client.AIError):
        client.run_task("drafting", "x")


def test_triage_rules():
    assert (
        triage_report(
            "Click here for crypto http://a http://b http://c", has_citation=False
        ).category
        == "spam"
    )
    t = triage_report("The dose of amoxicillin is wrong, should be 20 mg/kg", has_citation=False)
    assert t.category == "clinical" and t.escalate_to_clinician
    assert triage_report("Typo in option B", has_citation=False).category == "ok"
    assert triage_report("x", has_citation=False, duplicates_open=2).category == "duplicate"


@pytest.mark.django_db
def test_connection_test_falls_back_to_a_tiny_call_when_models_is_missing(monkeypatch):
    import urllib.error

    monkeypatch.setenv("AGENT_KEY", "k")
    p = make_provider(
        kind="agentrouter", base_url="https://agentrouter.org/v1", api_key_env="AGENT_KEY",
        default_model="m",
    )  # fmt: skip

    def no_models(*a, **k):
        raise urllib.error.HTTPError("u", 404, "nf", {}, None)

    monkeypatch.setattr(client.urllib.request, "urlopen", no_models)
    monkeypatch.setattr(client.safe_http, "assert_public_url", lambda u: None)
    reply = {
        "choices": [{"message": {"content": "pong"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    monkeypatch.setattr(client, "_call", lambda *a, **k: reply)
    ok, msg = client.check_connection(p)
    assert ok and "1-token" in msg
    assert AIUsage.objects.filter(task="conn-test", ok=True).count() == 1
