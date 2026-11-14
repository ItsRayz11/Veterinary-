import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.ai.models import AIProvider, AIUsage
from apps.automation.policy import looks_suspicious


def api(role):
    u, _ = User.objects.get_or_create(username=f"d-{role}", defaults={"role": role})
    c = APIClient()
    c.force_login(u)
    return c


@pytest.mark.django_db
def test_summary_scopes_extra_counts_by_role_and_ai_usage_aggregates():
    ed = api(Role.EDITOR).get("/api/v1/staff/summary/").json()
    assert "articles_in_review" in ed
    assert "catalogs_pending" not in ed and "ai_month_cost_usd" not in ed
    mod = api(Role.MODERATOR).get("/api/v1/staff/summary/").json()
    assert "catalogs_pending" in mod and "ai_month_cost_usd" not in mod
    p = AIProvider.objects.create(
        kind="openai", base_url="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY"
    )
    AIUsage.objects.create(
        provider=p, model="m", task="tagging", prompt_tokens=10, completion_tokens=5
    )
    adm = api(Role.ADMIN)
    assert adm.get("/api/v1/staff/summary/").json()["ai_month_calls"] == 1
    usage = adm.get("/api/v1/staff/ai/usage/").json()
    assert usage["month_calls"] == 1
    assert usage["by_task"][0]["tokens"] == 15


def test_payment_demand_postings_are_recognised():
    assert looks_suspicious("Great vet job! Pay a fee to apply via Western Union")
    assert not looks_suspicious("Veterinary officer, apply by 1 March")
