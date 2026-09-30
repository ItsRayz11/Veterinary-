from django.contrib import admin

from .models import AssistantLog


@admin.register(AssistantLog)
class AssistantLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "status", "question")
    list_filter = ("status", "model")
    search_fields = ("question", "answer")
    readonly_fields = [f.name for f in AssistantLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
