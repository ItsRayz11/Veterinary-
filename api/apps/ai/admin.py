from django.contrib import admin

from .models import AIProvider, AITaskRoute, AIUsage


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ("kind", "enabled", "api_key_env", "monthly_budget_usd", "last_test_ok")


@admin.register(AITaskRoute)
class AITaskRouteAdmin(admin.ModelAdmin):
    list_display = ("task", "provider", "model", "enabled")


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    list_display = ("at", "task", "provider", "model", "ok", "cost_usd")
    readonly_fields = [f.name for f in AIUsage._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
