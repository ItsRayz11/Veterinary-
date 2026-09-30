from django.contrib import admin

from .models import Job, ListingReport, Scholarship


class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "country", "status", "expires_on")
    list_filter = ("status", "country")
    search_fields = ("title", "organization")
    # Status changes go through the moderation service (audit log, no self-approval).
    readonly_fields = ("status", "expires_on", "moderated_by", "moderated_at", "moderation_note")


admin.site.register(Job, ListingAdmin)
admin.site.register(Scholarship, ListingAdmin)
admin.site.register(ListingReport, list_display=("content_type", "object_id", "reporter"))
