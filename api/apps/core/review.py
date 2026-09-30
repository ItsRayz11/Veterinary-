"""Verification workflow. The only sanctioned way to change a clinical record's review status."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import PUBLIC_STATUSES, SIGNED_OFF_STATUSES, AuditLog, ReviewStatus
from apps.sources.models import has_source

# Statuses that assert a claim about the data's provenance, so they need >= 1 linked Source.
NEEDS_SOURCE = PUBLIC_STATUSES | {ReviewStatus.PENDING_REVIEW}


@transaction.atomic
def set_review_status(record, new_status: str, by, reason: str = ""):
    """Move `record` to `new_status`, enforcing governance rules and writing an audit entry."""
    new_status = ReviewStatus(new_status)
    old_status = record.review_status

    if new_status in NEEDS_SOURCE and not (
        has_source(record) or getattr(record, "source_id", None)
    ):
        raise ValidationError("A source must be linked before this status can be set.")

    hook = getattr(record, "validate_publishable", None)
    if hook and new_status in PUBLIC_STATUSES:
        hook()  # model-specific readiness, e.g. a question needs exactly one correct option

    if new_status in SIGNED_OFF_STATUSES:
        if not by.can_approve_clinical:
            raise PermissionDenied(
                "Only veterinarian reviewers or admins can sign off clinical data."
            )
        if getattr(record, "submitted_by_id", None) == by.pk:
            raise PermissionDenied("Reviewer cannot approve their own submission.")
        if record.is_development_data:
            raise ValidationError("Development data can never be signed off.")

    if new_status == ReviewStatus.OFFICIAL_REGULATORY and not (
        by.can_approve_clinical or by.role in ("reviewer", "editor")
    ):
        raise PermissionDenied("Not allowed to mark a record as an official regulatory source.")

    record.review_status = new_status
    record.reviewed_by = by
    record.reviewed_at = timezone.now()
    record.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "updated_at"])

    AuditLog.objects.create(
        actor=by,
        action="review_status_changed",
        object_type=record._meta.label,
        object_id=str(record.pk),
        before={"review_status": old_status},
        after={"review_status": str(new_status)},
        reason=reason,
    )
    return record
