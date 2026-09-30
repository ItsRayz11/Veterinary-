from django.contrib import admin

from apps.core.admin_mixins import ReviewActionsMixin

from .models import Company, CompanyAlias


class AliasInline(admin.TabularInline):
    model = CompanyAlias
    extra = 0


@admin.register(Company)
class CompanyAdmin(ReviewActionsMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "country",
        "is_manufacturer",
        "is_importer",
        "is_distributor",
        "review_status",
    )
    list_filter = ("country", "review_status", "is_manufacturer", "is_importer", "is_distributor")
    search_fields = ("name", "normalized_name", "aliases__alias")
    inlines = [AliasInline]
