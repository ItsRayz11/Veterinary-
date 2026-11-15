"""Grouped, filterable view of the review backlog, built on the pipeline's RecordAssessment rows."""

import re
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.automation import assessment as A
from apps.automation import r2
from apps.automation.models import (
    DataSource,
    ImageAsset,
    ImageStatus,
    JobRun,
    RecordAssessment,
    RunStatus,
)
from apps.core.models import ReviewStatus
from apps.core.review import QUEUE_STATUSES, publishable_models

PAGE_SIZE = 25
QUEUE = [s.value for s in QUEUE_STATUSES]
FILTERS = {  # query-param -> RecordAssessment field
    "model": "model_key",
    "country": "country_iso2",
    "provider": "provider",
    "batch": "batch",
    "image": "image_state",
    "trust": "trust_level",
    "recommendation": "recommendation",
    "source": "source_state",
    "risk": "risk",
}
GROUPS = {  # group_by -> field (None = computed below)
    "type": "model_key",
    "country": "country_iso2",
    "provider": "provider",
    "batch": "batch",
    "status": "review_status",
    "image": "image_state",
    "trust": "trust_level",
    "recommendation": "recommendation",
    "source": "source_state",
    "issue": None,
    "completeness": None,
}
SOURCE_LABELS = {
    "none": "No source",
    "raw_url_only": "URL only (not linked)",
    "linked_unverified": "Linked, not verified",
    "linked_ok": "Linked and verified",
    "conflict": "Conflicting evidence",
    "invalid": "Invalid source",
}
IMAGE_LABELS = {
    "none": "No image",
    "pending": "Waiting to be stored",
    "stored": "Stored in R2",
    "failed": "Failed",
    "rejected": "Licence does not allow copying",
}
TRUST_LABELS = {"high": "High trust", "medium": "Medium trust", "low": "Low trust"}
BANDS = {"complete": (80, 101), "partial": (50, 80), "sparse": (0, 50)}
BAND_LABELS = {
    "complete": "Complete (80%+)",
    "partial": "Partly complete (50-79%)",
    "sparse": "Sparse (under 50%)",
}


def _model_label(key: str) -> str:
    m = publishable_models().get(key)
    return str(m._meta.verbose_name_plural).capitalize() if m else key


def filtered(params) -> "QuerySet[RecordAssessment]":  # noqa: F821
    """RecordAssessment rows matching the query parameters (default: records awaiting review)."""
    qs = RecordAssessment.objects.all()
    statuses = [s for s in (params.get("status") or "").split(",") if s]
    if not statuses and params.get("scope") != "all":
        statuses = QUEUE
    if statuses:
        qs = qs.filter(review_status__in=statuses)
    for param, field in FILTERS.items():
        val = params.get(param)
        if val:
            qs = qs.filter(**{field: val})
    if params.get("issue"):
        qs = qs.filter(issue_text__contains=f"|{params['issue']}|")
    if params.get("band") in BANDS:
        lo, hi = BANDS[params["band"]]
        qs = qs.filter(completeness__gte=lo, completeness__lt=hi)
    if params.get("duplicates") == "1":
        qs = qs.filter(issue_text__contains="|duplicate_candidate|")
    q = (params.get("q") or "").strip()[:100].lower()
    if q:
        m = re.fullmatch(r"([a-z_]+\.[a-z_]+):(\d+)", q)
        if m:
            qs = qs.filter(model_key=m.group(1), object_id=int(m.group(2)))
        else:
            cond = Q()
            for tok in q.split():
                part = Q(search_text__contains=tok)
                if tok.isdigit():
                    part |= Q(object_id=int(tok))
                cond &= part
            qs = qs.filter(cond)
    return qs


def serialize_item(a: RecordAssessment) -> dict:
    return {
        "model": a.model_key,
        "id": a.object_id,
        "label": a.label,
        "type": _model_label(a.model_key),
        "country": a.country_name,
        "country_iso2": a.country_iso2,
        "provider": a.provider,
        "batch": a.batch,
        "review_status": a.review_status,
        "is_development_data": a.is_development_data,
        "source_state": a.source_state,
        "has_source": a.source_state in ("linked_ok", "linked_unverified", "conflict", "invalid"),
        "trust": a.trust_level,
        "completeness": a.completeness,
        "issues": [{"code": c, "label": A.ISSUES.get(c, c)} for c in a.issues],
        "recommendation": a.recommendation,
        "recommendation_label": A.RECOMMENDATIONS.get(a.recommendation, a.recommendation),
        "image_state": a.image_state,
        "duplicates": len(a.duplicates),
        "updated_at": a.record_updated_at,
    }


def items(params, page: int, page_size: int = PAGE_SIZE) -> dict:
    qs = filtered(params).order_by("-record_updated_at", "-pk")
    total = qs.count()
    page = max(page, 1)
    start = (page - 1) * page_size
    return {
        "results": [serialize_item(a) for a in qs[start : start + page_size]],
        "count": total,
        "page": page,
        "page_size": page_size,
    }


def groups(params, by: str) -> list[dict]:
    qs = filtered({k: v for k, v in params.items() if k != by})
    if by == "issue":
        rows = []
        for code, label in A.ISSUES.items():
            n = qs.filter(issue_text__contains=f"|{code}|").count()
            if n:
                rows.append({"key": code, "label": label, "count": n})
        clean = qs.filter(issue_text="").count()
        if clean:
            rows.append({"key": "", "label": "No issues", "count": clean})
        return sorted(rows, key=lambda r: -r["count"])
    if by == "completeness":
        return [
            {"key": k, "label": BAND_LABELS[k], "count": n}
            for k, (lo, hi) in BANDS.items()
            if (n := qs.filter(completeness__gte=lo, completeness__lt=hi).count())
        ]
    field = GROUPS[by]
    extra = ("country_name",) if by == "country" else ()
    rows = []
    for r in qs.values(field, *extra).annotate(n=Count("pk")).order_by("-n"):
        key = r[field]
        rows.append({"key": key, "label": _label(by, key, r), "count": r["n"]})
    return rows


def _label(by: str, key: str, row: dict) -> str:
    if by == "type":
        return _model_label(key)
    if by == "country":
        return row.get("country_name") or "No country"
    if by == "status":
        return ReviewStatus(key).label if key in ReviewStatus.values else key
    if by == "recommendation":
        return A.RECOMMENDATIONS.get(key, key)
    labels = {"source": SOURCE_LABELS, "image": IMAGE_LABELS, "trust": TRUST_LABELS}.get(by)
    if labels:
        return labels.get(key, key)
    if by == "provider":
        return key or "Unknown"
    return key or "None"


def facets() -> dict:
    """Filter choices with counts (for the dropdowns), over the current queue."""
    qs = RecordAssessment.objects.filter(review_status__in=QUEUE)
    return {by: groups({}, by) for by in ("type", "country", "provider", "recommendation")} | {
        "total": qs.count()
    }


def overview() -> dict:
    now = timezone.now()
    queue = RecordAssessment.objects.filter(review_status__in=QUEUE)
    queue_total = sum(
        m.objects.filter(review_status__in=QUEUE).count() for m in publishable_models().values()
    )
    imported = sum(
        m.objects.filter(review_status=ReviewStatus.IMPORTED_UNVERIFIED).count()
        for m in publishable_models().values()
    )
    assets = ImageAsset.objects.exclude(status=ImageStatus.SUPERSEDED)
    by_image = {r["status"]: r["n"] for r in assets.values("status").annotate(n=Count("pk"))}
    import_tasks = ("universities-sync", "data-sources")
    last_ok = {
        t: JobRun.objects.filter(task=t, status=RunStatus.OK).order_by("-created_at").first()
        for t in (*import_tasks, "review-pipeline")
    }
    failed_runs = JobRun.objects.filter(
        status=RunStatus.FAILED, created_at__gte=now - timedelta(days=7)
    ).order_by("-created_at")
    held = DataSource.objects.exclude(held_reason="").count()
    ok_imports = [r.created_at for t, r in last_ok.items() if t in import_tasks and r]
    return {
        "total_imported": imported,
        "awaiting_review": queue_total,
        "assessed_in_queue": queue.count(),
        "not_yet_processed": max(queue_total - queue.count(), 0),
        "auto_processed": queue.filter(
            source_state="linked_ok", image_state__in=("none", "stored")
        ).count(),
        "source_problems": queue.filter(
            source_state__in=("none", "raw_url_only", "invalid", "conflict")
        ).count(),
        "duplicates": queue.filter(issue_text__contains="|duplicate_candidate|").count(),
        "safe_eligible": queue.filter(recommendation="safe_batch").count(),
        "images": {
            "stored": by_image.get("stored", 0),
            "pending": by_image.get("pending", 0),
            "failed": by_image.get("failed", 0),
            "rejected": by_image.get("rejected", 0),
        },
        "r2": {
            "configured": r2.configured(),
            "public_url": bool(r2.public_url_for("x")),
        },
        "failed_imports": {
            "runs_7d": failed_runs.count(),
            "held_sources": held,
            "recent": [
                {"task": r.task, "error": r.error, "at": r.created_at} for r in failed_runs[:5]
            ],
        },
        "last_successful_sync": max(ok_imports) if ok_imports else None,
        "last_runs": {t: (r.created_at if r else None) for t, r in last_ok.items()},
        "by_recommendation": {g["key"]: g["count"] for g in groups({}, "recommendation")},
    }
