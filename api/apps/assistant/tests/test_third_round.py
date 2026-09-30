"""Regression tests for the third code-review round."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.assistant import llm as llm_module
from apps.assistant import service
from apps.assistant.models import AnswerStatus
from apps.automation import tasks
from apps.automation.models import Feed
from apps.pharma.models import Generic


class FakeLLM:
    model = "fake"

    def __init__(self):
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        return json.dumps({"answer": "ok", "citations": ["G1"]})


@pytest.fixture
def world(db):
    call_command("seed_dev_catalog")
    return User.objects.create_user("asker", password="x")


def names(*n):
    for name in n:
        Generic.objects.create(name=name, is_development_data=True)


# ---- the model call must finish inside the 30 s function limit ----


def test_anthropic_client_uses_a_single_20_second_attempt(monkeypatch):
    seen = {}

    class FakeAnthropic:
        def __init__(self, **kw):
            seen.update(kw)

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
    llm_module.AnthropicLLM("key", "model")
    assert seen["timeout"] == 20.0 and seen["max_retries"] == 0


# ---- naming too many drugs is refused, not silently truncated ----


def test_question_naming_more_than_three_drugs_is_not_answered_from_a_subset(world):
    names("Alphacillin", "Betacillin", "Gammacillin")
    llm = FakeLLM()
    r = service.ask(world, "Compare alphacillin, betacillin, gammacillin and enrofloxacin", llm)
    assert r["status"] == AnswerStatus.TOO_MANY and llm.calls == 0
    assert "up to 3" in r["detail"] and r["answer"] == ""


def test_exactly_three_named_drugs_is_still_answered(world):
    names("Alphacillin", "Betacillin")
    llm = FakeLLM()
    r = service.ask(world, "Compare alphacillin, betacillin and enrofloxacin please", llm)
    assert r["status"] == AnswerStatus.ANSWERED and llm.calls == 1


# ---- the feed bot account cannot be squatted or used to log in ----


def test_feed_bot_username_cannot_be_registered_in_any_case(db):
    api = APIClient()
    for name in ("feed-bot", "Feed-Bot", " FEED-BOT "):
        r = api.post(
            "/api/v1/auth/register/",
            {
                "username": name,
                "email": f"{abs(hash(name))}@example.org",
                "password": "Zq7!kLm29xWv",
            },
            format="json",
        )
        assert r.status_code == 400, name
    assert not get_user_model().objects.filter(username__iexact="feed-bot").exists()


def test_a_squatted_bot_account_is_neutralised_when_automation_uses_it(db):
    squatter = User.objects.create_user("feed-bot", password="real-password-1")
    assert squatter.has_usable_password()
    bot = tasks.bot_user()
    bot.refresh_from_db()
    assert bot.pk == squatter.pk and not bot.has_usable_password()
    assert not APIClient().login(username="feed-bot", password="real-password-1")


# ---- feeds: overall deadline and consistent de-duplication ----


@pytest.fixture
def feed(db):
    call_command("seed_reference")
    return Feed.objects.create(
        name="F",
        url="https://feeds.example/f.xml",
        kind="jobs",
        organization="Org",
        default_job_type="full_time",
        license_note="ok",
        enabled=True,
    )


def test_feed_fetches_share_one_overall_deadline(feed, monkeypatch):
    seen = {"robots": None, "fetch": None}
    monkeypatch.setattr(
        tasks.safe_http,
        "allowed_by_robots",
        lambda url, **kw: seen.__setitem__("robots", kw.get("deadline")) or True,
    )
    monkeypatch.setattr(
        tasks.safe_http,
        "fetch",
        lambda url, **kw: (seen.__setitem__("fetch", kw.get("deadline")), (200, b"<rss/>", url))[1],
    )
    tasks.run_feed(feed)
    assert seen["robots"] is not None and seen["robots"] == seen["fetch"]


def test_links_longer_than_the_column_are_dropped_not_truncated():
    long_link = "https://example.org/" + "a" * (tasks.MAX_URL + 10)
    body = (
        "<rss><channel>"
        f"<item><title>Long</title><link>{long_link}</link></item>"
        "<item><title>Fine</title><link>https://example.org/ok</link></item>"
        "</channel></rss>"
    ).encode()
    assert [i["title"] for i in tasks.parse_feed(body)] == ["Fine"]


# ---- malformed request bodies are 400s ----


@pytest.mark.parametrize("body", [["a", "list"], "just a string", 42, None])
def test_non_object_json_bodies_are_rejected_with_400(world, body):
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    api = APIClient()
    api.force_login(editor)
    for url in (
        "/api/v1/staff/imports/",
        "/api/v1/assistant/ask/",
        "/api/v1/calculators/dilution/",
    ):
        r = api.post(url, body, format="json")
        assert r.status_code == 400, (url, r.status_code)
    assert APIClient().post("/api/v1/auth/login/", body, format="json").status_code == 400


def test_non_object_source_and_huge_csv_cell_are_validation_errors_not_500s(world):
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    api = APIClient()
    api.force_login(editor)
    csv_ok = "brand_name,generic_name,manufacturer\nA,Enrofloxacin,Co\n"
    r = api.post(
        "/api/v1/staff/imports/",
        {"country": "PK", "source": "a string", "csv_text": csv_ok},
        format="json",
    )
    assert r.status_code == 400 and "source" in r.json()["detail"].lower()
    huge = "brand_name,generic_name,manufacturer\n" + "x" * 200_000 + ",Enrofloxacin,Co\n"
    src = {"title": "T", "publisher": "P", "license_note": "n"}
    r = api.post(
        "/api/v1/staff/imports/",
        {"country": "PK", "source": src, "csv_text": huge},
        format="json",
    )
    assert r.status_code == 400 and "not valid CSV" in r.json()["detail"]


# ---- throttle scopes are separate ----


@override_settings()
def test_price_submissions_listings_and_reports_have_separate_throttle_scopes():
    from django.conf import settings

    from apps.opportunities.views import ReportThrottle
    from apps.opportunities.views import SubmitThrottle as ListingSubmit
    from apps.pricing.views import SubmitThrottle as PriceSubmit

    scopes = {PriceSubmit.scope, ListingSubmit.scope, ReportThrottle.scope}
    assert len(scopes) == 3
    assert scopes <= set(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
