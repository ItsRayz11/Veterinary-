import json
from datetime import date

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.automation.models import DataSource
from apps.content import trends
from apps.species.models import Species


def fake_fetch(recent, prior):
    def fetch(url, **kw):
        start, end = url.rstrip("/").split("/")[-2:]  # the API's own date window
        items = [
            {"timestamp": f"{start}00", "views": prior},
            {"timestamp": f"{end}00", "views": recent},
        ]
        return 200, json.dumps({"items": items}).encode(), url

    return fetch


def test_views_split_into_recent_and_prior_windows():
    v = trends.views("Cat", today=date(2026, 12, 1), fetch=fake_fetch(300, 100))
    assert v == (300, 100)


def test_trending_only_returns_real_growth_with_evidence_link():
    out = trends.trending(["Cat"], fetch=fake_fetch(300, 100))
    assert out
    assert out[0]["growth_pct"] == 200
    assert out[0]["evidence_url"].startswith("https://en.wikipedia.org/")
    assert trends.trending(["Cat"], fetch=fake_fetch(50, 100)) == []  # falling: not a trend
    assert trends.trending(["Cat"], fetch=lambda *a, **k: (500, b"", "")) == []


@pytest.mark.django_db
def test_trend_ideas_need_source_registered_and_terms_confirmed(monkeypatch):
    Species.objects.create(slug="cat", name="Cat")
    ed = APIClient()
    ed.force_login(User.objects.create_user("ed", password="x", role=Role.EDITOR))
    r = ed.post("/api/v1/staff/articles/suggest-topics/").json()
    assert "Trend ideas skipped" in r["note"]
    DataSource.objects.filter(slug="wikimedia-pageviews").update(
        enabled=True, terms_confirmed_at=timezone.now()
    )
    hit = {
        "topic": "Cat",
        "recent": 300,
        "prior": 100,
        "growth_pct": 200,
        "evidence_url": "https://en.wikipedia.org/wiki/Cat",
    }
    monkeypatch.setattr(trends, "trending", lambda names, **k: [hit])
    r = ed.post("/api/v1/staff/articles/suggest-topics/").json()
    assert "Trend ideas skipped" not in r["note"]
    topics = ed.get("/api/v1/staff/topics/").json()["results"]
    assert any(t["basis"] == "verified_trend" and "+200%" in t["rationale"] for t in topics)
