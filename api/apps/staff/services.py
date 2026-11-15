"""Queue queries for the staff review panel. Status changes always go through apps.core.review."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q

from apps.core.models import ReviewStatus
from apps.core.review import QUEUE_STATUSES, publishable_models, set_review_status
from apps.sources.models import has_source, sources_for


def get_record(model_key: str, pk: int):
    model = publishable_models().get(model_key)
    if model is None:
        return None
    return model.objects.filter(pk=pk).first()


def queue_counts() -> dict[str, int]:
    statuses = [s.value for s in QUEUE_STATUSES]
    return {
        key: n
        for key, m in publishable_models().items()
        if (n := m.objects.filter(review_status__in=statuses).count())
    }


def serialize_record(model_key: str, obj) -> dict:
    return {
        "model": model_key,
        "id": obj.pk,
        "label": str(obj),
        "review_status": obj.review_status,
        "is_development_data": obj.is_development_data,
        "has_source": has_source(obj) or bool(getattr(obj, "source_id", None)),
        "updated_at": obj.updated_at,
    }


def change_status(model_key: str, pk: int, status: str, by, reason: str):
    """Returns (record, error_message, http_status)."""
    obj = get_record(model_key, pk)
    if obj is None:
        return None, "Record not found.", 404
    if status not in ReviewStatus.values:
        return None, "Unknown status.", 400
    try:
        set_review_status(obj, status, by, reason=reason)
    except PermissionDenied as exc:
        return None, str(exc), 403
    except ValidationError as exc:
        return None, " ".join(exc.messages), 400
    return obj, "", 200


def history_diff(obj) -> list[dict]:
    """Field-level changes between consecutive historical versions, newest first."""
    records = list(obj.history.all().order_by("-history_date", "-history_id"))
    out = []
    for new, old in zip(records, records[1:], strict=False):
        delta = new.diff_against(old)
        out.append(
            {
                "date": new.history_date,
                "by": getattr(new.history_user, "username", None),
                "changes": [
                    {"field": c.field, "old": str(c.old), "new": str(c.new)} for c in delta.changes
                ],
            }
        )
    if records:
        first = records[-1]
        out.append(
            {
                "date": first.history_date,
                "by": getattr(first.history_user, "username", None),
                "changes": [],
                "created": True,
            }
        )
    return out


PAGE_SIZE = 25
_NAME_FIELDS = ("name", "brand_name", "title", "stem", "registration_number", "alias", "synonym")


def _search_filter(model, q: str) -> Q:
    names = {f.name for f in model._meta.concrete_fields}
    cond = Q()
    for field in _NAME_FIELDS:
        if field in names:
            cond |= Q(**{f"{field}__icontains": q})
    return cond


def queue_page(model_key: str, statuses: list[str], q: str, page: int) -> dict:
    """One page of the review queue, newest first, optionally one model and a text search."""
    models = publishable_models()
    page = max(page, 1)
    total, items = 0, []
    for key, m in models.items():
        if model_key and key != model_key:
            continue
        qs = m.objects.filter(review_status__in=statuses)
        if q:
            cond = _search_filter(m, q)
            if not cond:
                continue
            qs = qs.filter(cond)
        total += qs.count()
        # Enough rows from each model to fill this page after merging.
        for obj in qs.order_by("-updated_at", "-pk")[: page * PAGE_SIZE]:
            items.append(serialize_record(key, obj))
    items.sort(key=lambda i: (i["updated_at"], i["id"]), reverse=True)
    start = (page - 1) * PAGE_SIZE
    return {
        "results": items[start : start + PAGE_SIZE],
        "count": total,
        "page": page,
        "page_size": PAGE_SIZE,
    }


_URL_FIELDS = {"website", "source_url", "image_url", "image_page_url", "image_license_url"}
_SECTIONS = {
    "universities.university": [
        ("Institution", ["name", "country", "city", "founded_year", "website"]),
        ("Location", ["latitude", "longitude"]),
        ("Description", ["summary"]),
        ("Provenance", ["wikidata_id", "source_url", "source_license"]),
    ],
}


def _field_value(obj, f) -> str:
    value = getattr(obj, f.name, None)
    if f.is_relation:
        value = str(value) if value is not None else ""
    return "" if value is None else str(value)


def _item(f: dict) -> dict:
    is_url = f["name"] in _URL_FIELDS and f["value"].lower().startswith(("http://", "https://"))
    return {"label": f["field"], "value": f["value"], "is_url": is_url}


def _sections(model_key: str, fields: list[dict]) -> list[dict]:
    """Reviewer-friendly grouping: academic sections for universities, one list otherwise."""
    by_name = {f["name"]: f for f in fields}
    layout = _SECTIONS.get(model_key)
    if not layout:
        return [{"title": "Details", "items": [_item(f) for f in fields]}]
    used, out = set(), []
    for title, names in layout:
        items = [_item(by_name[n]) for n in names if n in by_name]
        used.update(names)
        if items:
            out.append({"title": title, "items": items})
    rest = [_item(f) for n, f in by_name.items() if n not in used and not n.startswith("image_")]
    if rest:
        out.append({"title": "Other", "items": rest})
    return out


def _source_payload(s, health) -> dict:
    return {
        "id": s.pk,
        "title": s.title,
        "publisher": s.publisher,
        "url": s.url,
        "license_note": s.license_note,
        "license_url": s.license_url,
        "source_type": s.source_type,
        "provider": s.provider,
        "verification_status": s.verification_status,
        "verification_note": s.verification_note,
        "verified_at": s.verified_at,
        "accessed_date": s.accessed_date,
        "health": (
            {
                "ok": health.ok,
                "status_code": health.status_code,
                "checked_at": health.checked_at,
                "error": health.error,
            }
            if health
            else None
        ),
    }


def _image_payload(a) -> dict:
    from apps.automation import images as img
    from apps.automation.models import ImageStatus

    return {
        "id": a.pk,
        "original_url": a.original_url,
        "display_url": img.display_url(a),
        "page_url": a.page_url,
        "credit": a.credit,
        "license": a.license,
        "license_url": a.license_url,
        "status": a.status,
        "status_detail": a.status_detail,
        "attempts": a.attempts,
        "mime_type": a.mime_type,
        "size_bytes": a.size_bytes,
        "sha256": a.sha256,
        "in_r2": a.status == ImageStatus.STORED and bool(a.object_key),
        "stored_at": a.stored_at,
        "duplicate_of": a.duplicate_of_id,
    }


def record_detail(model_key: str, pk: int) -> dict | None:
    """Everything a reviewer needs in one place: the data, its linked sources, images and their
    R2 status, the pipeline's assessment, timestamps and the audit trail."""
    from django.contrib.contenttypes.models import ContentType

    from apps.automation import assessment as A
    from apps.automation import r2
    from apps.automation.models import ImageAsset, ImageStatus, RecordAssessment, SourceHealth
    from apps.core.models import AuditLog

    obj = get_record(model_key, pk)
    if obj is None:
        return None
    fields = [
        {"name": f.name, "field": f.verbose_name.capitalize(), "value": _field_value(obj, f)[:1500]}
        for f in obj._meta.concrete_fields
        if f.name not in {"id", "created_at", "updated_at"} and not f.name.startswith("normalized_")
    ]
    linked = list(sources_for(obj)[:10])
    health = {h.source_id: h for h in SourceHealth.objects.filter(source__in=linked)}
    ct = ContentType.objects.get_for_model(obj)
    assets = ImageAsset.objects.filter(content_type=ct, object_id=obj.pk).exclude(
        status=ImageStatus.SUPERSEDED
    )
    assessed = RecordAssessment.objects.filter(content_type=ct, object_id=obj.pk).first()
    if assessed is None:
        assessed = A.assess(obj)
    audit = AuditLog.objects.filter(object_type=obj._meta.label, object_id=str(obj.pk))[:30]
    website = getattr(obj, "website", "") or ""
    return {
        **serialize_record(model_key, obj),
        "fields": [{"field": f["field"], "value": f["value"]} for f in fields],
        "sections": _sections(model_key, fields),
        "type": str(obj._meta.verbose_name).capitalize(),
        "country": assessed.country_name,
        "description": getattr(obj, "summary", "") or getattr(obj, "description", "") or "",
        "website": website if website.lower().startswith(("http://", "https://")) else "",
        "raw_source_url": getattr(obj, "source_url", "") or "",
        "sources": [_source_payload(s, health.get(s.pk)) for s in linked],
        "images": [_image_payload(a) for a in assets],
        "r2_configured": r2.configured(),
        "assessment": {
            "completeness": assessed.completeness,
            "missing_fields": assessed.missing_fields,
            "issues": [{"code": c, "label": A.ISSUES.get(c, c)} for c in assessed.issues],
            "duplicates": assessed.duplicates,
            "recommendation": assessed.recommendation,
            "recommendation_label": A.RECOMMENDATIONS.get(
                assessed.recommendation, assessed.recommendation
            ),
            "reasons": assessed.reasons,
            "trust": assessed.trust_level,
            "risk": assessed.risk,
            "source_state": assessed.source_state,
            "provider": assessed.provider,
            "batch": assessed.batch,
            "changed_fields": assessed.changed_fields,
            "changed_at": assessed.changed_at,
            "assessed_at": assessed.assessed_at,
        },
        "timeline": {
            "imported_at": obj.created_at,
            "last_synced_at": obj.updated_at,
            "reviewed_at": obj.reviewed_at,
            "reviewed_by": getattr(obj.reviewed_by, "username", None),
        },
        "audit": [
            {
                "at": e.at,
                "actor": getattr(e.actor, "username", None),
                "action": e.action.replace("_", " "),
                "before": e.before,
                "after": e.after,
                "reason": e.reason,
            }
            for e in audit
        ],
    }
