from django.contrib import admin

from .models import SearchMiss


@admin.register(SearchMiss)
class SearchMissAdmin(admin.ModelAdmin):
    list_display = ("query", "example", "count", "last_seen", "resolved")
    list_filter = ("resolved",)
    search_fields = ("query",)
    ordering = ("-count",)
