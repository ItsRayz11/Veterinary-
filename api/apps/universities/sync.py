"""Scheduled import of veterinary schools: one country per run, oldest first.

Shared by the `import_universities` command and the `universities-sync` automation task. Rows are
always created as `imported_unverified`; a record an editor has already reviewed is never touched.
A run covers a single country so it fits the serverless time limit; the schedule walks the list.
"""

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


def next_country() -> str | None:
    """The mapped country that was synced longest ago (never-synced first)."""
    from apps.automation.models import JobRun

    last: dict[str, float] = {}
    for run in JobRun.objects.filter(task="universities-sync", status="ok").order_by("created_at"):
        iso2 = (run.summary or {}).get("country")
        if iso2:
            last[iso2] = run.created_at.timestamp()
    candidates = [c for c in UNIVERSITY_SOURCES if Country.objects.filter(iso2=c).exists()]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c in last, last.get(c, 0.0)))


def sync_next_country(fetch=None) -> dict:
    iso2 = next_country()
    if iso2 is None:
        return {"country": None, "note": "no mapped country exists in the database"}
    return sync_country(iso2, fetch)
