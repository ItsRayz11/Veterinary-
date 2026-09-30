"""Moderation and reporting rules for jobs and scholarships."""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.models import AuditLog

from .models import Job, Listing, ListingReport, ListingStatus, Scholarship

KINDS = {"jobs": Job, "scholarships": Scholarship}
MODERATOR_ROLES = {Role.MODERATOR, Role.ADMIN}
REPORTS_TO_UNPUBLISH = 3
MAX_PENDING_PER_USER = 5


def _check_moderator(user):
    if not (user.is_superuser or user.role in MODERATOR_ROLES):
        raise PermissionDenied("Only moderators can moderate listings.")


def _audit(user, action, obj, before, after, reason=""):
    AuditLog.objects.create(
        actor=user,
        action=action,
        object_type=obj._meta.label,
        object_id=str(obj.pk),
        before={"status": before},
        after={"status": after},
        reason=reason,
    )


def check_can_submit(user, model) -> None:
    """Cap the moderation backlog one account can create."""
    if model.objects.filter(submitted_by=user, status=ListingStatus.PENDING).count() >= (
        MAX_PENDING_PER_USER
    ):
        raise ValidationError(
            f"You already have {MAX_PENDING_PER_USER} listings waiting for review."
        )


@transaction.atomic
def approve(listing: Listing, by, note: str = "") -> Listing:
    _check_moderator(by)
    if listing.status != ListingStatus.PENDING:
        raise ValidationError("This listing was already moderated.")
    if listing.submitted_by_id == by.pk:
        raise PermissionDenied("Moderators cannot approve their own submissions.")
    today = timezone.localdate()
    if listing.closes_on and listing.closes_on < today:
        raise ValidationError("The closing date has already passed.")
    listing.expires_on = Listing.default_expiry(listing.closes_on, today)
    listing.status = ListingStatus.APPROVED
    listing.moderated_by, listing.moderated_at = by, timezone.now()
    listing.moderation_note = note[:300]
    listing.save()
    # Reports made before this review are settled by it: clearing them lets the same users report
    # again later and stops old reports counting towards the next automatic unpublish.
    cleared, _ = ListingReport.objects.filter(
        content_type=ContentType.objects.get_for_model(listing), object_id=listing.pk
    ).delete()
    _audit(by, "listing_approved", listing, "pending", "approved", note)
    if cleared:
        AuditLog.objects.create(
            actor=by,
            action="listing_reports_cleared",
            object_type=listing._meta.label,
            object_id=str(listing.pk),
            after={"reports_cleared": cleared},
            reason=note[:300],
        )
    return listing


@transaction.atomic
def reject(listing: Listing, by, note: str) -> Listing:
    _check_moderator(by)
    if listing.status == ListingStatus.REJECTED:
        raise ValidationError("This listing was already rejected.")
    if not note.strip():
        raise ValidationError("A reason is required when rejecting a listing.")
    before = listing.status
    listing.status = ListingStatus.REJECTED
    listing.moderated_by, listing.moderated_at = by, timezone.now()
    listing.moderation_note = note.strip()[:300]
    listing.save()
    _audit(by, "listing_rejected", listing, before, "rejected", note)
    return listing


@transaction.atomic
def report(listing: Listing, user, message: str) -> int:
    """Record a report on a live listing. Enough distinct reporters send it back to moderation."""
    if listing.status != ListingStatus.APPROVED:
        raise ValidationError("Only live listings can be reported.")
    if not message.strip():
        raise ValidationError("Describe the problem.")
    if listing.submitted_by_id == user.pk:
        raise ValidationError("You cannot report your own listing.")
    ct = ContentType.objects.get_for_model(listing)
    try:
        with transaction.atomic():
            ListingReport.objects.create(
                content_type=ct, object_id=listing.pk, reporter=user, message=message.strip()[:300]
            )
    except IntegrityError as exc:
        raise ValidationError("You already reported this listing.") from exc
    count = ListingReport.objects.filter(content_type=ct, object_id=listing.pk).count()
    if count >= REPORTS_TO_UNPUBLISH:
        listing.status = ListingStatus.PENDING
        listing.moderation_note = f"Sent back for review after {count} user reports."
        listing.save()
        _audit(user, "listing_unpublished_by_reports", listing, "approved", "pending")
    return count
