"""Scheduled import of veterinary schools: as many countries per run as the time budget allows,
oldest first.

Shared by the `import_universities` command and the `universities-sync` automation task. Rows are
always created as `imported_unverified`; a record an editor has already reviewed is never touched.
A run stops starting new countries before the serverless time limit; the schedule walks the list.
"""

import time

from apps.core.models import ReviewStatus
from apps.core.reference_data import UNIVERSITY_SOURCES
from apps.core.text import normalize_name
from apps.countries.models import Country

from . import importer
from .models import University

# The summary text is Wikipedia's; the licence is recorded with it.
TEXT_LICENSE = "CC BY-SA 4.0 (Wikipedia)"


def store_row(country, row: dict) -> str:
    """Create or refresh one imported row. Returns 'created', 'updated' or 'skipped'."""
    row = dict(row)
    image = row.pop("image") or {}
    fields = {
        **row,
        "source_license": TEXT_LICENSE,
        "image_url": image.get("url", ""),
        "image_page_url": image.get("page_url", ""),
        "image_credit": image.get("credit", ""),
        "image_license": image.get("license", ""),
        "image_license_url": image.get("license_url", ""),
    }
    existing = University.objects.filter(
        country=country, normalized_name=normalize_name(row["name"])
    ).first()
    if existing is None:
        University.objects.create(
            country=country, review_status=ReviewStatus.IMPORTED_UNVERIFIED, **fields
        )
        return "created"
    if existing.review_status != ReviewStatus.IMPORTED_UNVERIFIED:
        return "skipped"
    for k, v in fields.items():
        setattr(existing, k, v)
    existing.save()
    return "updated"


def sync_country(iso2: str, fetch=None) -> dict:
    country = Country.objects.filter(iso2=iso2).first()
    if country is None:
        return {"country": iso2, "error": "country not in the database"}
    rows = importer.collect(fetch or importer.api_fetch, iso2)
    counts = {"created": 0, "updated": 0, "skipped": 0}
    for row in rows:
        counts[store_row(country, row)] += 1
    return {"country": iso2, **counts}


def next_country(exclude: frozenset[str] = frozenset()) -> str | None:
    """The mapped country that was synced longest ago (never-synced first), skipping `exclude`."""
    from apps.automation.models import JobRun

    last: dict[str, float] = {}
    for run in JobRun.objects.filter(task="universities-sync", status="ok").order_by("created_at"):
        summary = run.summary or {}
        # Runs record every country they covered; older runs recorded a single "country".
        for iso2 in summary.get("countries") or [summary.get("country")]:
            if iso2:
                last[iso2] = run.created_at.timestamp()
    candidates = [
        c
        for c in UNIVERSITY_SOURCES
        if c not in exclude and Country.objects.filter(iso2=c).exists()
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c in last, last.get(c, 0.0)))


def sync_next_country(fetch=None) -> dict:
    iso2 = next_country()
    if iso2 is None:
        return {"country": None, "note": "no mapped country exists in the database"}
    return sync_country(iso2, fetch)


# Vercel stops the function at 30 s. A new country starts only if the slowest one so far would
# still finish inside the budget.
SYNC_BUDGET_SECONDS = 20
MAX_COUNTRIES_PER_RUN = 8


def sync_countries(
    fetch=None, budget_seconds: float = SYNC_BUDGET_SECONDS, clock=time.monotonic
) -> dict:
    """Sync the oldest countries one after another until the time budget is nearly used."""
    started, slowest = clock(), 0.0
    last_exc: Exception | None = None
    done: list[dict] = []
    while len(done) < MAX_COUNTRIES_PER_RUN:
        elapsed = clock() - started
        if done and elapsed + slowest * 1.5 > budget_seconds:
            break
        iso2 = next_country(exclude=frozenset(d["country"] for d in done))
        if iso2 is None:
            break
        t0 = clock()
        try:
            done.append(sync_country(iso2, fetch))
        except Exception as exc:  # noqa: BLE001 - one country must not lose the others' results
            done.append({"country": iso2, "error": f"{type(exc).__name__}: {exc}"[:200]})
            last_exc = exc
        slowest = max(slowest, clock() - t0)
    if not done:
        return {
            "country": None,
            "countries": [],
            "note": "no mapped country exists in the database",
        }
    if last_exc is not None and all(d.get("error") for d in done):
        raise last_exc  # nothing worked: the run is recorded as failed and shows on the dashboard
    totals = {k: sum(d.get(k, 0) for d in done) for k in ("created", "updated", "skipped")}
    countries = [d["country"] for d in done if not d.get("error")]
    return {"country": done[0]["country"], "countries": countries, **totals, "runs": done}
