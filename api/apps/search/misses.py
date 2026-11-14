"""Zero-result search logging (privacy-light: normalised text and a counter only)."""

import re

from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

from .models import SearchMiss

MAX_ROWS = 20_000  # a flood of random strings cannot grow the table without bound
SKIP = re.compile(r"@|https?:|www\.|\d{6,}")  # emails, links, long numbers: never stored


def record_miss(raw: str, normalized: str) -> None:
    """Count one failed search. Never raises: logging must not break searching."""
    try:
        if not normalized or SKIP.search(raw):
            return
        key = normalized[:100]
        updated = SearchMiss.objects.filter(query=key).update(
            count=F("count") + 1, last_seen=timezone.now(), resolved=False
        )
        if updated or SearchMiss.objects.count() >= MAX_ROWS:
            return
        try:
            SearchMiss.objects.create(query=key, example=raw.strip()[:100])
        except IntegrityError:
            SearchMiss.objects.filter(query=key).update(count=F("count") + 1)
    except Exception:  # noqa: BLE001, S110 - best effort by design
        return


def top_misses(limit: int = 50, include_resolved: bool = False) -> list[dict]:
    qs = SearchMiss.objects.all()
    if not include_resolved:
        qs = qs.filter(resolved=False)
    return [
        {
            "id": m.pk,
            "query": m.query,
            "example": m.example,
            "count": m.count,
            "first_seen": m.first_seen,
            "last_seen": m.last_seen,
            "resolved": m.resolved,
        }
        for m in qs[:limit]
    ]
