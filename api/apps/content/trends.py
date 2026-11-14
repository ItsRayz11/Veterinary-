"""Trend signals from the Wikimedia Pageviews API (public, official, CC0 data).

Used only when an admin has registered and approved the source in the registry
(slug `wikimedia-pageviews`: enabled, not paused, terms confirmed). It measures general public
interest in a topic's Wikipedia page, a rough popularity signal, not veterinary-specific demand.
The numbers are real API values shown with the evidence link; nothing is estimated.
"""

import json
import time
from datetime import date, timedelta
from urllib.parse import quote

from apps.automation import safe_http
from apps.automation.models import DataSource

SOURCE_SLUG = "wikimedia-pageviews"
API = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "en.wikipedia/all-access/user/{title}/daily/{start}/{end}"
)
WINDOW = 30
BUDGET_SECONDS = 15


def source_ready() -> tuple[DataSource | None, str]:
    s = DataSource.objects.filter(slug=SOURCE_SLUG).first()
    if s is None:
        return None, "The Wikimedia Pageviews source is not registered."
    if s.paused or not s.enabled:
        return None, "The Wikimedia Pageviews source is paused or disabled."
    if not s.terms_confirmed_at:
        return None, "Confirm the Wikimedia terms in the source registry to use trend data."
    return s, ""


def page_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="_")


def views(title: str, today: date | None = None, fetch=safe_http.fetch) -> tuple[int, int] | None:
    """(views in the last 30 days, views in the 30 days before). None if unavailable."""
    end = (today or date.today()) - timedelta(days=1)  # today's data is incomplete
    start = end - timedelta(days=2 * WINDOW - 1)
    url = API.format(
        title=quote(title.replace(" ", "_"), safe="_"),
        start=f"{start:%Y%m%d}",
        end=f"{end:%Y%m%d}",
    )
    try:
        status, body, _ = fetch(url, timeout=6, deadline=time.monotonic() + 8)
        if status != 200:
            return None
        items = json.loads(body)["items"]
    except (safe_http.FetchError, ValueError, KeyError):
        return None
    cutoff = f"{end - timedelta(days=WINDOW - 1):%Y%m%d}00"
    recent = sum(i["views"] for i in items if i["timestamp"] >= cutoff)
    prior = sum(i["views"] for i in items if i["timestamp"] < cutoff)
    if recent + prior == 0:
        return None
    return recent, prior


def trending(titles: list[str], limit: int = 5, fetch=safe_http.fetch) -> list[dict]:
    """Rising topics first. Each result carries the real numbers and the evidence link."""
    started = time.monotonic()
    out = []
    for title in titles:
        if time.monotonic() - started > BUDGET_SECONDS:
            break
        v = views(title, fetch=fetch)
        if not v or v[0] <= v[1] or v[1] == 0:
            continue
        recent, prior = v
        out.append(
            {
                "topic": title,
                "recent": recent,
                "prior": prior,
                "growth_pct": round((recent - prior) * 100 / prior),
                "evidence_url": page_url(title),
            }
        )
    return sorted(out, key=lambda r: r["growth_pct"], reverse=True)[:limit]
