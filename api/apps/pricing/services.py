"""Moderation workflow for price submissions."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.models import AuditLog

from .models import (
    PriceOrigin,
    PriceRecord,
    PriceSubmission,
    SubmissionKind,
    SubmissionStatus,
)

MODERATOR_ROLES = {Role.MODERATOR, Role.ADMIN}
SCREEN_REFERENCES = 50  # most recent published prices compared against


def screen_submission(sub: PriceSubmission) -> dict:
    """Compare a new-price submission with published prices for the same pack, country,
    currency and price type. Advisory only: a moderator still decides; nothing is approved or
    rejected here. Pure arithmetic (median), no AI."""
    from apps.automation.policy import is_price_outlier

    empty = {"references": 0, "median": None, "outlier": False}
    if sub.kind != SubmissionKind.NEW_PRICE or sub.amount is None:
        return empty
    currency = sub.currency or sub.country.currency_code
    amounts = [
        float(a)
        for a in PriceRecord.objects.published()
        .filter(
            pack_id=sub.pack_id,
            country_id=sub.country_id,
            currency=currency,
            price_type=sub.price_type,
        )
        .order_by("-observed_on")
        .values_list("amount", flat=True)[:SCREEN_REFERENCES]
    ]
    if not amounts:
        return empty
    ordered = sorted(amounts)
    median = ordered[len(ordered) // 2]
    return {
        "references": len(amounts),
        "median": f"{median:.2f}",
        "outlier": is_price_outlier(float(sub.amount), amounts),
    }


def _check_moderator(user):
    if not (user.is_superuser or user.role in MODERATOR_ROLES):
        raise PermissionDenied("Only moderators can moderate price submissions.")


def _finish(sub: PriceSubmission, status, by, note, before):
    sub.status = status
    sub.moderated_by = by
    sub.moderated_at = timezone.now()
    sub.moderation_note = note[:300]
    sub.save(
        update_fields=["status", "moderated_by", "moderated_at", "moderation_note", "updated_at"]
    )
    AuditLog.objects.create(
        actor=by,
        action=f"price_submission_{status}",
        object_type=sub._meta.label,
        object_id=str(sub.pk),
        before={"status": before},
        after={"status": status},
        reason=note,
    )


@transaction.atomic
def approve_submission(sub: PriceSubmission, by, note: str = "") -> PriceRecord | None:
    """Approve. A new price becomes a published record; an error report flags the target."""
    _check_moderator(by)
    if sub.status != SubmissionStatus.PENDING:
        raise ValidationError("Submission was already moderated.")
    if sub.submitted_by_id == by.pk:
        raise PermissionDenied("Moderators cannot approve their own submissions.")
    record = None
    if sub.kind == SubmissionKind.NEW_PRICE:
        currency = sub.currency or sub.country.currency_code
        record = PriceRecord.objects.create(
            pack=sub.pack,
            country=sub.country,
            region=sub.region,
            city=sub.city,
            currency=currency,
            price_type=sub.price_type,
            amount=sub.amount,
            origin=PriceOrigin.USER_SUBMITTED,
            observed_on=timezone.localdate(),
            verified_at=timezone.now(),
            submitted_by=sub.submitted_by,
            confidence="0.60",  # community-sourced, moderator-checked
            is_published=True,
        )
    elif sub.kind == SubmissionKind.REPORT_INCORRECT and sub.target_id:
        # Report accepted: withdraw the disputed price from public view (history row is kept).
        sub.target.is_published = False
        sub.target.save(update_fields=["is_published", "updated_at"])
    _finish(sub, SubmissionStatus.APPROVED, by, note, SubmissionStatus.PENDING)
    return record


@transaction.atomic
def reject_submission(sub: PriceSubmission, by, note: str) -> None:
    _check_moderator(by)
    if sub.status != SubmissionStatus.PENDING:
        raise ValidationError("Submission was already moderated.")
    if not note:
        raise ValidationError("A reason is required when rejecting a submission.")
    _finish(sub, SubmissionStatus.REJECTED, by, note, SubmissionStatus.PENDING)
