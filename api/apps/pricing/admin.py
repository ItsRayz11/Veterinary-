from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError

from . import services
from .models import PriceRecord, PriceSubmission


@admin.register(PriceRecord)
class PriceRecordAdmin(admin.ModelAdmin):
    list_display = ("pack", "country", "price_type", "currency", "amount", "origin", "is_published")
    list_filter = ("country", "price_type", "origin", "is_published")
    search_fields = ("pack__product__brand_name",)
    autocomplete_fields = ()
    list_select_related = ("pack__product", "country")

    def has_change_permission(self, request, obj=None):
        return obj is None  # append-only: add new rows instead of editing


@admin.action(description="Approve selected submissions")
def approve(modeladmin, request, queryset):
    for sub in queryset:
        try:
            services.approve_submission(sub, request.user)
        except (PermissionDenied, ValidationError) as exc:
            modeladmin.message_user(request, f"{sub}: {exc}", messages.ERROR)


@admin.action(description="Reject selected submissions (reason: rejected by moderator)")
def reject(modeladmin, request, queryset):
    for sub in queryset:
        try:
            services.reject_submission(sub, request.user, "Rejected by moderator")
        except (PermissionDenied, ValidationError) as exc:
            modeladmin.message_user(request, f"{sub}: {exc}", messages.ERROR)


@admin.register(PriceSubmission)
class PriceSubmissionAdmin(admin.ModelAdmin):
    list_display = ("pack", "kind", "amount", "currency", "status", "submitted_by", "created_at")
    list_filter = ("status", "kind", "country")
    actions = [approve, reject]
    readonly_fields = ("status", "moderated_by", "moderated_at", "moderation_note")
