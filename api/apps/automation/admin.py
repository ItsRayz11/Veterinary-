from django.contrib import admin

from .models import Feed, JobRun, SourceHealth


@admin.register(Feed)
class FeedAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "enabled", "last_run_at", "last_result")
    list_filter = ("kind", "enabled")
    readonly_fields = ("robots_confirmed_at", "last_checksum", "last_run_at", "last_result")


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
