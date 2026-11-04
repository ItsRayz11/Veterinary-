from django.contrib import admin, messages

from apps.accounts.models import Role

from . import datasources
from .models import DataSource, Feed, JobRun, SourceHealth


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "enabled", "last_run_at", "last_result")
    list_filter = ("kind", "enabled")
    readonly_fields = ("robots_confirmed_at", "last_checksum", "last_run_at", "last_result")


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "country_iso2",
        "enabled",
        "reachable",
        "update_available",
        "last_checked_at",
        "importer",
        "import_enabled",
        "terms_confirmed_at",
        "last_imported_at",
        "last_import_result",
        "consecutive_failures",
    )
    list_filter = ("enabled", "last_ok", "update_available", "import_enabled", "kind")
    search_fields = ("name", "publisher", "slug")
    readonly_fields = (
        "terms_confirmed_at",
        "terms_confirmed_by",
        "last_checked_at",
        "last_ok",
        "last_http_status",
        "last_error",
        "consecutive_failures",
        "fingerprint",
        "last_changed_at",
        "update_available",
        "imported_fingerprint",
        "last_imported_at",
        "last_import_result",
    )
    actions = ["check_now", "confirm_terms_checked", "acknowledge_update"]

    @admin.display(boolean=True, description="Reachable")
    def reachable(self, obj):
        return obj.last_ok

    @admin.action(description="Check selected sources now")
    def check_now(self, request, queryset):
        cache: dict = {}
        for source in queryset:
            datasources.check_source(source, cache)
        self.message_user(request, f"Checked {queryset.count()} source(s).")

    @admin.action(description="I have read the publisher's terms and reuse is allowed")
    def confirm_terms_checked(self, request, queryset):
        if not (request.user.is_superuser or request.user.role == Role.ADMIN):
            self.message_user(request, "Only admins can confirm terms.", messages.ERROR)
            return
        for source in queryset:
            datasources.confirm_terms(source, request.user)
        self.message_user(request, f"Terms confirmed for {queryset.count()} source(s).")

    @admin.action(description="Mark update as seen")
    def acknowledge_update(self, request, queryset):
        queryset.update(update_available=False)


@admin.register(JobRun)
class JobRunAdmin(admin.ModelAdmin):
    list_display = ("task", "status", "created_at", "finished_at")
    list_filter = ("task", "status")

    def has_add_permission(self, request):
        return False


@admin.register(SourceHealth)
class SourceHealthAdmin(admin.ModelAdmin):
    list_display = ("source", "ok", "status_code", "consecutive_failures", "checked_at")
    list_filter = ("ok",)

    def has_add_permission(self, request):
        return False
