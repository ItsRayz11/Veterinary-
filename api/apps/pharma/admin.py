from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.core.admin_mixins import ReviewActionsMixin

from . import models


class GenericSynonymInline(admin.TabularInline):
    model = models.GenericSynonym
    extra = 0


class ProductIngredientInline(admin.TabularInline):
    model = models.ProductIngredient
    extra = 0


class ProductPackInline(admin.TabularInline):
    model = models.ProductPack
    extra = 0


class RegistrationInline(admin.TabularInline):
    model = models.ProductRegistration
    extra = 0
    fields = ("country", "registration_number", "status", "review_status")
    readonly_fields = ("review_status",)


@admin.register(models.Generic)
class GenericAdmin(ReviewActionsMixin, SimpleHistoryAdmin):
    list_display = ("name", "drug_class", "review_status", "is_development_data")
    list_filter = ("review_status", "is_development_data", "drug_class")
    search_fields = ("name", "normalized_name", "synonyms__synonym")
    filter_horizontal = ("ingredients",)
    inlines = [GenericSynonymInline]


@admin.register(models.Product)
class ProductAdmin(ReviewActionsMixin, SimpleHistoryAdmin):
    list_display = ("brand_name", "generic", "manufacturer", "review_status", "is_development_data")
    list_filter = ("review_status", "is_development_data", "manufacturer__country")
    search_fields = ("brand_name", "normalized_brand_name", "generic__name")
    autocomplete_fields = ("generic", "manufacturer", "marketing_holder")
    inlines = [ProductIngredientInline, ProductPackInline, RegistrationInline]
    list_select_related = ("generic", "manufacturer")


@admin.register(models.ProductRegistration)
class RegistrationAdmin(ReviewActionsMixin, SimpleHistoryAdmin):
    list_display = ("product", "country", "registration_number", "status", "review_status")
    list_filter = ("country", "status", "review_status")
    search_fields = ("registration_number", "product__brand_name")


admin.site.register(models.DrugClass)
admin.site.register(models.Ingredient, search_fields=("name",))
admin.site.register(models.DosageForm)
