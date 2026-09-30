from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError

from .models import ReviewStatus
from .review import set_review_status

READONLY_REVIEW_FIELDS = ("review_status", "reviewed_by", "reviewed_at")


def _make_action(status: ReviewStatus):
    @admin.action(description=f"Set review status: {status.label}")
    def action(modeladmin, request, queryset):
        done = 0
        for obj in queryset:
            try:
                set_review_status(obj, status, request.user, reason="admin action")
                done += 1
            except (PermissionDenied, ValidationError) as exc:
                msg = "; ".join(getattr(exc, "messages", [str(exc)]))
                modeladmin.message_user(request, f"{obj}: {msg}", messages.ERROR)
        if done:
            modeladmin.message_user(request, f"{done} record(s) updated.", messages.SUCCESS)

    action.__name__ = f"mark_{status.value}"
    return action


class ReviewActionsMixin:
    """Status is read-only in forms; changes go through the governed review service."""

    readonly_fields = READONLY_REVIEW_FIELDS
    actions = [
        _make_action(s)
        for s in (
            ReviewStatus.PENDING_REVIEW,
            ReviewStatus.MANUFACTURER_SUPPLIED,
            ReviewStatus.OFFICIAL_REGULATORY,
            ReviewStatus.EXPERT_REVIEWED,
            ReviewStatus.VERIFIED,
            ReviewStatus.NEEDS_VERIFICATION,
            ReviewStatus.DEPRECATED,
            ReviewStatus.ARCHIVED,
        )
    ]
