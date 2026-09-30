"""Queue queries for the staff review panel. Status changes always go through apps.core.review."""

from django.apps import apps as django_apps
from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.models import PublishableModel, ReviewStatus
from apps.core.review import set_review_status
from apps.sources.models import has_source

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
