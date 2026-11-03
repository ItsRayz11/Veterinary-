from django.contrib import admin

from apps.core.admin_mixins import ReviewActionsMixin

from .models import University


@admin.register(University)
class UniversityAdmin(ReviewActionsMixin, admin.ModelAdmin):
    list_display = ("name", "country", "city", "review_status")
    list_filter = ("country", "review_status")
    search_fields = ("name", "normalized_name", "city", "wikidata_id")
