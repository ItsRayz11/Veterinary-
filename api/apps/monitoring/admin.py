from django.contrib import admin

from .models import ClientError


@admin.register(ClientError)
class ClientErrorAdmin(admin.ModelAdmin):
    list_display = ("message", "path", "count", "last_seen", "resolved")
    list_filter = ("resolved",)
    search_fields = ("message", "path")
    readonly_fields = [f.name for f in ClientError._meta.fields]

    def has_add_permission(self, request):
        return False
