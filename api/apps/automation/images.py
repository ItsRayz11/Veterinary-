"""Image pipeline: find image references, decide whether copying is permitted, store in R2.

Rules, in order, for every reference:
  1. https URL only.
  2. The licence must be an open one (apps.core.licensing). Unknown, non-free or fair-use = never
     copied. A reference is still recorded so staff can see why.
  3. Licences that require attribution (CC BY, BY-SA) also need the credit and a link back
     (file page), which are stored with the object and shown wherever the image is.
  4. Download through the SSRF-hardened fetcher, size-capped, and the bytes must really be a
     raster image of an allowed type (magic bytes, not just the Content-Type header). SVG is
     refused: it can carry script.
  5. Content-addressed key (sha256), so duplicates are detected and stored once.
Nothing is uploaded unless R2 is configured; until then rows simply stay `pending`.
"""

import hashlib
from collections.abc import Callable
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.licensing import is_open_license, requires_attribution

from . import r2, safe_http
from .models import ImageAsset, ImageStatus

MAX_BYTES = 5 * 1024 * 1024
MAX_ATTEMPTS = 3
ALLOWED = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}

Fetcher = Callable[[str], tuple[int, bytes, dict]]


def sniff_mime(data: bytes) -> str:
    """The real image type from magic bytes ('' if it is not an allowed raster image)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return ""


def permission(url: str, license_name: str, credit: str, page_url: str) -> tuple[bool, str]:
    """May we copy this image? (allowed, reason when not)."""
    if not (url or "").lower().startswith("https://"):
        return False, "Image address is not an https URL."
    if not is_open_license(license_name):
        return False, f"Licence '{license_name or 'unknown'}' does not allow redistribution."
    if requires_attribution(license_name) and not (credit.strip() and page_url.strip()):
        return False, "Licence requires attribution but the credit or file page is missing."
    return True, ""


def references(record) -> list[dict]:
    """Image references the record carries (currently the university image_* fields)."""
    url = (getattr(record, "image_url", "") or "").strip()
    if not url:
        return []
    return [
        {
            "original_url": url,
            "page_url": getattr(record, "image_page_url", "") or "",
            "credit": getattr(record, "image_credit", "") or "",
            "license": getattr(record, "image_license", "") or "",
            "license_url": getattr(record, "image_license_url", "") or "",
        }
    ]


@transaction.atomic
def discover(record) -> list[ImageAsset]:
    """Create/refresh ImageAsset rows for the record's references. Idempotent: an asset that is
    already stored or retried keeps its state unless its licence evidence changed."""
    ct = ContentType.objects.get_for_model(record)
    refs = references(record)
    current = {r["original_url"] for r in refs}
    ImageAsset.objects.filter(content_type=ct, object_id=record.pk).exclude(
        original_url__in=current
    ).exclude(status=ImageStatus.SUPERSEDED).update(
        status=ImageStatus.SUPERSEDED, status_detail="The record now references another image."
    )
    out = []
    for ref in refs:
        allowed, why = permission(
            ref["original_url"], ref["license"], ref["credit"], ref["page_url"]
        )
        asset, created = ImageAsset.objects.get_or_create(
            content_type=ct,
            object_id=record.pk,
            original_url=ref["original_url"],
            defaults={
                **{k: v for k, v in ref.items() if k != "original_url"},
                "status": ImageStatus.PENDING if allowed else ImageStatus.REJECTED,
                "status_detail": why,
            },
        )
        if not created:
            evidence = {k: v for k, v in ref.items() if k != "original_url"}
            changed = any(getattr(asset, k) != v for k, v in evidence.items())
            for k, v in evidence.items():
                setattr(asset, k, v)
            if changed or asset.status == ImageStatus.SUPERSEDED:
                if not allowed:
                    asset.status, asset.status_detail = ImageStatus.REJECTED, why
                elif asset.status in (ImageStatus.REJECTED, ImageStatus.SUPERSEDED):
                    asset.status, asset.status_detail, asset.attempts = (
                        ImageStatus.PENDING,
                        "",
                        0,
                    )
            asset.save()
        out.append(asset)
    return out


def _default_fetcher(url: str) -> tuple[int, bytes, dict]:
    status, body, _final, headers = safe_http.fetch_full(url, max_bytes=MAX_BYTES, timeout=10)
    return status, body, headers


def _fail(asset: ImageAsset, detail: str) -> ImageAsset:
    asset.status, asset.status_detail = ImageStatus.FAILED, detail[:300]
    asset.attempts += 1
    asset.last_attempt_at = timezone.now()
    asset.save()
    return asset


def process(
    asset: ImageAsset, *, fetcher: Fetcher | None = None, transport: r2.Transport | None = None
) -> ImageAsset:
    """Download and store one pending/failed asset. Never raises: failures are recorded on the row
    so they show in the admin and can be retried."""
    if asset.status not in (ImageStatus.PENDING, ImageStatus.FAILED):
        return asset
    allowed, why = permission(asset.original_url, asset.license, asset.credit, asset.page_url)
    if not allowed:  # evidence may have been edited since discovery
        asset.status, asset.status_detail = ImageStatus.REJECTED, why
        asset.save()
        return asset
    if not r2.configured():
        asset.status_detail = "Cloudflare R2 is not configured on the server; image not copied."
        asset.save(update_fields=["status_detail", "updated_at"])
        return asset
    try:
        status, body, headers = (fetcher or _default_fetcher)(asset.original_url)
    except safe_http.FetchError as exc:
        return _fail(asset, f"Download failed: {exc}")
    if status != 200:
        return _fail(asset, f"Download failed (HTTP {status}).")
    if len(body) > MAX_BYTES:
        return _fail(asset, "Image is larger than the 5 MB limit.")
    if not body:
        return _fail(asset, "The download was empty.")
    mime = sniff_mime(body)
    if not mime:
        return _fail(asset, "Not an allowed image type (JPEG, PNG, WebP or GIF).")
    declared = (headers.get("content-type", "") or "").split(";")[0].strip().lower()
    if declared and declared in ALLOWED and declared != mime:
        return _fail(asset, f"Content-Type {declared} does not match the file ({mime}).")

    digest = hashlib.sha256(body).hexdigest()
    first = (
        ImageAsset.objects.filter(sha256=digest, status=ImageStatus.STORED)
        .exclude(pk=asset.pk)
        .order_by("pk")
        .first()
    )
    asset.mime_type, asset.size_bytes, asset.sha256 = mime, len(body), digest
    asset.last_attempt_at = timezone.now()
    if first is not None:  # same bytes already in R2: reuse the object, do not upload again
        asset.object_key, asset.duplicate_of = first.object_key, first
        asset.status, asset.status_detail = (
            ImageStatus.STORED,
            "Identical to an image already stored.",
        )
        asset.stored_at = timezone.now()
        asset.save()
        return asset
    key = f"images/{digest[:2]}/{digest}.{ALLOWED[mime]}"
    try:
        r2.put_object(
            key,
            body,
            mime,
            {
                "source-url": asset.original_url,
                "attribution-url": asset.page_url,
                "credit": asset.credit,
                "license": asset.license,
                "license-url": asset.license_url,
                "sha256": digest,
                "record": f"{asset.content_type.model}:{asset.object_id}",
            },
            transport=transport,
        )
    except r2.R2Error as exc:
        return _fail(asset, str(exc))
    asset.object_key, asset.status, asset.status_detail = key, ImageStatus.STORED, ""
    asset.stored_at = timezone.now()
    asset.save()
    return asset


def retry(asset: ImageAsset, **kw) -> ImageAsset:
    """Staff-triggered retry: resets the attempt counter, then processes once."""
    if asset.status == ImageStatus.FAILED:
        asset.attempts = 0
        asset.save(update_fields=["attempts", "updated_at"])
    return process(asset, **kw)


def retry_due(now) -> Q:
    """Failed assets whose backoff has passed: 1, 2, then 4 days after attempts 1, 2, 3...
    Re-running the pipeline by hand cannot use up the attempts in minutes; a staff "Retry" in the
    admin (`retry`) still works at any time."""
    due = Q(pk__in=[])
    for n in range(1, MAX_ATTEMPTS):
        due |= Q(attempts=n, last_attempt_at__lte=now - timedelta(days=2 ** (n - 1)))
    return Q(status=ImageStatus.FAILED, attempts__lt=MAX_ATTEMPTS) & (
        due | Q(attempts=0) | Q(last_attempt_at__isnull=True)
    )


def process_pending(limit: int = 5, budget_seconds: float = 12.0, **kw) -> dict:
    """Process eligible assets (pending first, then failed with attempts left) within a budget."""
    import time

    started = time.monotonic()
    done = failed = 0
    qs = ImageAsset.objects.filter(
        Q(status=ImageStatus.PENDING) | retry_due(timezone.now())
    ).order_by("status", "attempts", "pk")  # 'failed' < 'pending' alphabetically; re-sorted below
    batch = sorted(
        qs[: limit * 4], key=lambda a: (a.status != ImageStatus.PENDING, a.attempts, a.pk)
    )
    for asset in batch[:limit]:
        if time.monotonic() - started > budget_seconds:
            break
        out = process(asset, **kw)
        done += out.status == ImageStatus.STORED
        failed += out.status == ImageStatus.FAILED
    return {"stored": done, "failed": failed, "r2_configured": r2.configured()}


def display_url(asset: ImageAsset) -> str:
    """What an admin preview should load: the R2 copy when public, else the original."""
    if asset.status == ImageStatus.STORED:
        return r2.public_url_for(asset.object_key) or asset.original_url
    return asset.original_url
