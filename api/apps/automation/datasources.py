"""Watching and importing external data sources (see DataSource).

`check_data_sources` is the scheduled task: for each due source it reads the public URL (robots.txt
honoured, short deadlines, one source never aborts the run) and records reachability and whether
the publisher's file changed. It never touches the catalogue.

`sync_source` is the import, run from `manage.py sync_data_sources` (too long for a 30 s
serverless function). It needs an importer, `import_enabled` and confirmed terms, and everything it
creates is staged and approved only into the *unreviewed* state (never `public()`; catalogue pages
show such records labelled and noindex only when SHOW_UNVERIFIED_IMPORTS is on).
"""

import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone

from apps.countries.models import Country
from apps.ingestion import services
from apps.ingestion.adapters import ca_dpd, common, uk_vmd
from apps.ingestion.models import ImportBatch
from apps.sources.models import Source

from . import safe_http
from .models import DataSource

CHECK_BUDGET = 12  # seconds for the whole scheduled run (Vercel stops functions at 30 s)
CHECK_LIMIT = 10
PROBE_TIMEOUT = 5
PROBE_DEADLINE = 8
DOWNLOAD_MAX_BYTES = 40_000_000
DOWNLOAD_DEADLINE = 120


@dataclass(frozen=True)
class Importer:
    label: str
    iso2: str  # country the records belong to (resolved from the Country table)
    run: Callable[[bytes], common.Cleaned]


IMPORTERS: dict[str, Importer] = {
    "uk-vmd": Importer("UK VMD Product Information Database", "GB", uk_vmd.clean_snapshot),
    "ca-dpd": Importer("Health Canada Drug Product Database", "CA", ca_dpd.clean_extract),
}

_LAST_UPDATED = re.compile(r'"last_updated"\s*:\s*"([^"]+)"')


def _fingerprint(headers: dict[str, str], body: bytes = b"") -> str:
    """Something that changes when the publisher's file changes; empty when we cannot tell."""
    parts = [
        headers.get("etag", ""),
        headers.get("last-modified", ""),
        headers.get("content-length", ""),
    ]
    if any(parts[:2]):  # validators are trustworthy; a bare length is too weak on its own
        return "|".join(parts)[:200]
    if body and "json" in headers.get("content-type", ""):
        match = _LAST_UPDATED.search(body[:20000].decode("utf-8", errors="replace"))
        if match:
            return f"last_updated:{match.group(1)}"[:200]
    return ""


def check_source(source: DataSource, robots_cache: dict | None = None) -> DataSource:
    """Read the source's public URL once and record the outcome."""
    now = timezone.now()
    url = source.check_url
    deadline = time.monotonic() + PROBE_DEADLINE
    ok, status, error, fingerprint = None, None, "", ""
    try:
        if not safe_http.allowed_by_robots(
            url, timeout=PROBE_TIMEOUT, cache=robots_cache, deadline=deadline
        ):
            error = "skipped: robots.txt forbids automated access or could not be read"
        else:
            status, _, _, headers = safe_http.fetch_full(
                url, method="HEAD", timeout=PROBE_TIMEOUT, deadline=deadline
            )
            body = b""
            if status in (403, 405, 501) or (
                status == 200 and "json" in headers.get("content-type", "")
            ):
                try:  # some servers refuse HEAD; small JSON APIs carry their own update date
                    status, body, _, headers = safe_http.fetch_full(
                        url, method="GET", timeout=PROBE_TIMEOUT, deadline=deadline
                    )
                except safe_http.FetchError as exc:
                    if "larger than" not in str(exc):
                        raise
                    status = 200
            ok = status < 400
            error = "" if ok else f"HTTP {status}"
            fingerprint = _fingerprint(headers, body) if ok else ""
    except safe_http.FetchError as exc:
        ok, error = False, str(exc)[:300]

    source.last_checked_at = now
    source.last_ok = ok
    source.last_http_status = status
    source.last_error = error[:300]
    # A robots refusal is not an outage: it neither counts as a failure nor clears one.
    if ok is False:
        source.consecutive_failures = min(source.consecutive_failures + 1, 32000)
    elif ok:
        source.consecutive_failures = 0
    if ok and fingerprint:
        changed = bool(source.fingerprint) and fingerprint != source.fingerprint
        if changed:
            source.last_changed_at = now
        source.fingerprint = fingerprint
        if source.importer:
            source.update_available = fingerprint != source.imported_fingerprint
        elif changed:
            source.update_available = True
    source.save()
    return source


def check_data_sources(
    limit: int = CHECK_LIMIT, budget_seconds: float = CHECK_BUDGET, clock=time.monotonic
) -> dict:
    """Check enabled sources that are due, never-checked first, within the time budget."""
    started = clock()
    now = timezone.now()
    due = DataSource.objects.filter(enabled=True).order_by(
        F("last_checked_at").asc(nulls_first=True), "pk"
    )
    summary = {"checked": 0, "reachable": 0, "failed": 0, "changed": 0, "stopped_early": False}
    cache: dict = {}
    for source in due:
        interval = timedelta(hours=source.check_interval_hours)
        if source.last_checked_at and now - source.last_checked_at < interval:
            continue
        if summary["checked"] >= limit or clock() - started > budget_seconds:
            summary["stopped_early"] = True
            break
        before = source.last_changed_at
        try:
            check_source(source, cache)
        except Exception as exc:  # noqa: BLE001 - one broken source must not starve the rest
            source.last_checked_at, source.last_ok = now, False
            source.last_error = f"unexpected {type(exc).__name__}"[:300]
            source.save(update_fields=["last_checked_at", "last_ok", "last_error", "updated_at"])
        summary["checked"] += 1
        summary["reachable"] += bool(source.last_ok)
        summary["failed"] += source.last_ok is False
        summary["changed"] += source.last_changed_at != before
    return summary


def confirm_terms(source: DataSource, user) -> DataSource:
    source.terms_confirmed_at, source.terms_confirmed_by = timezone.now(), user
    source.save(update_fields=["terms_confirmed_at", "terms_confirmed_by", "updated_at"])
    return source


class SyncError(Exception):
    """A sync that cannot or should not run; the message is safe to show staff."""


def sync_source(source: DataSource, *, log: Callable[[str], None] = lambda _m: None) -> dict:
    """Download the source's file and push it through the reviewed import pipeline."""
    importer = IMPORTERS.get(source.importer)
    if importer is None:
        raise SyncError(f"{source.name} has no importer (monitor only).")
    if not source.import_enabled:
        raise SyncError(f"Import is not enabled for {source.name}.")
    if not source.terms_confirmed_at:
        raise SyncError(f"Confirm the publisher's terms for {source.name} before importing.")
    country = Country.objects.filter(iso2=importer.iso2).first()
    if country is None:
        raise SyncError(f"Country {importer.iso2} is missing; run `manage.py seed_reference`.")
    deadline = time.monotonic() + DOWNLOAD_DEADLINE
    if not safe_http.allowed_by_robots(source.data_url, deadline=deadline):
        raise SyncError("robots.txt does not allow automated access to this file.")
    try:
        status, body, _final, headers = safe_http.fetch_full(
            source.data_url, max_bytes=DOWNLOAD_MAX_BYTES, timeout=60, deadline=deadline
        )
    except safe_http.FetchError as exc:
        raise SyncError(f"Download failed: {exc}") from exc
    if status != 200:
        raise SyncError(f"Download failed: HTTP {status}")
    try:
        cleaned = importer.run(body)
    except Exception as exc:  # noqa: BLE001 - a changed file layout must read as a clear error
        raise SyncError(
            f"The file could not be read ({type(exc).__name__}); layout changed?"
        ) from exc
    if not cleaned.rows:
        raise SyncError("The file produced no usable rows; refusing to import.")

    user = services.import_user()
    parts = common.chunks(cleaned.rows)
    totals = {"staged": 0, "approved": 0, "flagged": 0, "batches": 0}
    for i, part in enumerate(parts, start=1):
        csv_text = common.to_csv(part)
        title = f"{source.name} (part {i}/{len(parts)})"
        batch = ImportBatch.objects.filter(
            kind="products", country=country, checksum=_sha(csv_text)
        ).first()
        if batch is None:
            try:
                batch = services.stage_batch(
                    user=user,
                    country=country,
                    source_data={
                        "title": title,
                        "publisher": source.publisher,
                        "url": source.landing_url,
                        "license_note": source.licence_note,
                        "source_type": "regulatory",
                    },
                    csv_text=csv_text,
                    file_name=f"{source.slug}-{i}.csv",
                )
            except ValidationError as exc:
                raise SyncError(" ".join(exc.messages)) from exc
            totals["staged"] += batch.rows.count()
        totals["batches"] += 1
        stalled = 0
        while True:
            result = services.approve_clean(batch, user)
            totals["approved"] += result["approved"]
            totals["flagged"] += result["skipped"]
            log(f"  {title}: approved {totals['approved']}, flagged {totals['flagged']}")
            if result["remaining"] == 0:
                break
            stalled = stalled + 1 if (result["approved"] + result["skipped"]) == 0 else 0
            if stalled >= 3:
                break
    provenance = Source.objects.create(
        source_type="regulatory",
        title=f"{source.name} (synchronised {timezone.localdate():%Y-%m-%d})",
        publisher=source.publisher,
        url=source.landing_url,
        license_note=source.licence_note,
        country=country,
        accessed_date=timezone.localdate(),
        checksum=_sha(source.fingerprint or str(len(cleaned.rows))),
    )
    recon = services.reconcile_registrations(
        country, provenance, cleaned.rows, cleaned.expired_numbers, user
    )
    totals.update(recon)
    summary = (
        f"{totals['staged']} new rows staged, {totals['approved']} approved as unreviewed, "
        f"{totals['flagged']} flagged; {recon['status_changed']} status changes, "
        f"{recon['species_added']} target species added, "
        f"{recon['registrations_added']} extra authorisations"
    )
    source.imported_fingerprint = _fingerprint(headers) or source.fingerprint
    source.fingerprint = source.imported_fingerprint or source.fingerprint
    source.update_available = False
    source.last_imported_at = timezone.now()
    source.last_import_result = summary[:300]
    source.save()
    return {**totals, "report": cleaned.report}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def due_for_import() -> list[DataSource]:
    """Importable sources whose publisher file changed (or was never imported)."""
    return list(
        DataSource.objects.filter(import_enabled=True, terms_confirmed_at__isnull=False)
        .exclude(importer="")
        .filter(Q(update_available=True) | Q(last_imported_at__isnull=True))
    )


STALE_AFTER = timedelta(days=14)
FAILURES_BEFORE_ALERT = 3


def source_problems(now=None) -> list[str]:
    """Human-readable alerts: sources failing repeatedly, or import-enabled ones gone stale."""
    now = now or timezone.now()
    out = []
    for s in DataSource.objects.filter(enabled=True):
        if s.consecutive_failures >= FAILURES_BEFORE_ALERT:
            out.append(
                f"{s.slug}: unreachable {s.consecutive_failures} checks in a row ({s.last_error})"
            )
        if s.import_enabled and (not s.last_imported_at or now - s.last_imported_at > STALE_AFTER):
            out.append(f"{s.slug}: last successful import is older than {STALE_AFTER.days} days")
        if s.last_import_result.startswith("failed"):
            out.append(f"{s.slug}: last import failed ({s.last_import_result})")
    return out


__all__ = ["IMPORTERS", "check_data_sources", "check_source", "confirm_terms", "sync_source"]
