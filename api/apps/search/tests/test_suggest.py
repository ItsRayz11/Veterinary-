import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.ai.client import AIError
from apps.core.models import AuditLog, ReviewStatus
from apps.pharma.models import Generic, GenericSynonym
from apps.search import suggest
from apps.search.models import SearchMiss
from apps.search.services import search

pytestmark = pytest.mark.django_db


@pytest.fixture
def generic():
    call_command("seed_reference")
    return Generic.objects.create(
        name="Albendazole", review_status=ReviewStatus.OFFICIAL_REGULATORY
    )


@pytest.fixture
def editor():
    return User.objects.create_user("ed", password="x", role=Role.EDITOR)


def miss(text):
    search(text)
    return SearchMiss.objects.get(example=text)


def test_misspelling_gets_a_spelling_suggestion(generic):
    m = miss("albendazle tablets")
    assert suggest.spelling_suggestions(m)[0] == {
        "slug": generic.slug,
        "name": "Albendazole",
        "via": "spelling",
    }


def test_accepting_adds_an_audited_synonym_so_the_next_search_finds_it(generic, editor):
    m = miss("albendazle")
    synonym = suggest.accept(m, generic.slug, editor)
    m.refresh_from_db()
    assert m.resolved and synonym.generic == generic and synonym.synonym == "albendazle"
    log = AuditLog.objects.get(action="search_synonym_added")
    assert log.actor == editor and log.after == {"synonym": "albendazle", "generic": generic.slug}
    assert [g["name"] for g in search("albendazle")["generics"]] == ["Albendazole"]


def test_accept_refuses_hidden_generics_and_conflicting_synonyms(generic, editor):
    hidden = Generic.objects.create(
        name="Hiddenzole", review_status=ReviewStatus.NEEDS_VERIFICATION
    )
    other = Generic.objects.create(
        name="Fenbendazole", review_status=ReviewStatus.OFFICIAL_REGULATORY
    )
    m = miss("zzbendazole")
    with pytest.raises(Exception, match="not in the public catalogue"):
        suggest.accept(m, hidden.slug, editor)
    GenericSynonym.objects.create(generic=other, synonym="zzbendazole")
    with pytest.raises(Exception, match="already a synonym of Fenbendazole"):
        suggest.accept(m, generic.slug, editor)
    assert not GenericSynonym.objects.filter(generic=generic).exists()


def test_ai_answer_is_used_only_when_that_generic_is_listed(generic, monkeypatch):
    m = miss("valbazen")
    answers = iter(["Albendazole.", "Fenbendazole", "UNKNOWN"])
    monkeypatch.setattr(suggest, "_ask", lambda *a, **k: next(answers))
    hit = suggest.ai_suggestion(m)
    assert hit["suggestions"] == [{"slug": generic.slug, "name": "Albendazole", "via": "ai"}]
    unknown_to_us = suggest.ai_suggestion(m)
    assert unknown_to_us["suggestions"] == [] and "not in the catalogue" in unknown_to_us["note"]
    assert suggest.ai_suggestion(m)["suggestions"] == []
    assert not GenericSynonym.objects.exists()  # nothing is added without a person


def test_staff_api_lists_suggestions_accepts_and_reports_ai_unavailable(generic, editor):
    m = miss("albendazle")
    client = APIClient()
    client.force_authenticate(editor)
    row = client.get("/api/v1/staff/search-misses/").json()["results"][0]
    assert row["suggestions"][0]["slug"] == generic.slug
    ai = client.post(f"/api/v1/staff/search-misses/{m.pk}/ai-suggest/")
    assert ai.status_code == 503 and ai.json()["detail"]  # no provider configured in tests
    ok = client.post(f"/api/v1/staff/search-misses/{m.pk}/accept/", {"generic": generic.slug})
    assert ok.status_code == 200 and ok.json()["resolved"] is True
    bad = client.post(f"/api/v1/staff/search-misses/{m.pk}/accept/", {"generic": "nope"})
    assert bad.status_code == 400


def test_ai_errors_are_safe_to_show(generic, monkeypatch):
    def boom(*a, **k):
        raise AIError("Provider returned HTTP 429.")

    monkeypatch.setattr(suggest, "_ask", boom)
    with pytest.raises(AIError, match="429"):
        suggest.ai_suggestion(miss("valbazen"))


def test_without_a_tagging_route_ask_ai_uses_claude_and_says_when_nothing_is_set_up(
    generic, monkeypatch, settings
):
    class FakeClaude:
        model = "claude-opus-5-5"

        def complete(self, system, user):
            assert "INN" in system and user == "valbazen"
            return "Albendazole"

    monkeypatch.setattr("apps.assistant.llm.get_llm", lambda: FakeClaude())
    m = miss("valbazen")
    assert suggest.ai_suggestion(m)["suggestions"][0]["via"] == "ai"

    monkeypatch.setattr("apps.assistant.llm.get_llm", lambda: None)
    with pytest.raises(AIError, match="ANTHROPIC_API_KEY"):
        suggest.ai_suggestion(m)


def test_an_admin_routed_provider_wins_over_the_default(generic, monkeypatch):
    from apps.ai.models import AIProvider, AITaskRoute

    provider = AIProvider.objects.create(
        kind="openrouter", base_url="https://openrouter.ai/api/v1", enabled=True
    )
    AITaskRoute.objects.create(task="tagging", provider=provider, model="any-model")
    monkeypatch.setattr("apps.ai.client.run_task", lambda *a, **k: "Albendazole")
    monkeypatch.setattr(
        "apps.assistant.llm.get_llm", lambda: (_ for _ in ()).throw(AssertionError("not used"))
    )
    assert suggest.ai_suggestion(miss("valbazen"))["suggestions"][0]["slug"] == generic.slug
