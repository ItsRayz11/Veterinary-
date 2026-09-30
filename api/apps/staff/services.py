"""Queue queries for the staff review panel. Status changes always go through apps.core.review."""

from django.apps import apps as django_apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q

from apps.core.models import PublishableModel, ReviewStatus
from apps.core.review import set_review_status
from apps.sources.models import has_source, sources_for

QUEUE_STATUSES = (
    ReviewStatus.COMMUNITY_SUBMITTED,
    ReviewStatus.NEEDS_VERIFICATION,
    ReviewStatus.PENDING_REVIEW,
)


def publishable_models() -> dict[str, type]:
    """{'pharma.generic': Generic, ...} for every model with a review status."""
    return {
        m._meta.label_lower: m
        for m in django_apps.get_models()
        if issubclass(m, PublishableModel) and not m._meta.abstract
    }


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


def record_detail(model_key: str, pk: int) -> dict | None:
    """What a reviewer needs to judge a record: its fields and where its data came from."""
    obj = get_record(model_key, pk)
    if obj is None:
        return None
    fields = []
    for f in obj._meta.concrete_fields:
        if f.name in {"id", "created_at", "updated_at"} or f.name.startswith("normalized_"):
            continue
        value = getattr(obj, f.name, None)
        if f.is_relation:
            value = str(value) if value is not None else ""
        text = "" if value is None else str(value)
        fields.append({"field": f.verbose_name.capitalize(), "value": text[:500]})
    sources = [
        {
            "title": s.title,
            "publisher": s.publisher,
            "url": s.url,
            "license_note": s.license_note,
            "source_type": s.source_type,
        }
        for s in sources_for(obj)[:10]
    ]
    return {**serialize_record(model_key, obj), "fields": fields, "sources": sources}
