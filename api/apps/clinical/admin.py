from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.core.admin_mixins import ReviewActionsMixin

from . import models

CLINICAL_FILTERS = ("review_status", "is_development_data")


@admin.register(models.DoseRegimen)
class DoseAdmin(ReviewActionsMixin, SimpleHistoryAdmin):
    list_display = (
        "generic",
        "species",
        "route",
        "dose_min",
        "dose_max",
        "dose_unit",
        "review_status",
    )
    list_filter = (*CLINICAL_FILTERS, "species", "route")
    search_fields = ("generic__name",)
    autocomplete_fields = ("generic", "product")


@admin.register(models.WithdrawalPeriod)
class WithdrawalAdmin(ReviewActionsMixin, SimpleHistoryAdmin):
    list_display = (
        "product",
        "country",
        "species",
        "commodity",
        "duration_value",
        "duration_unit",
        "review_status",
    )
    list_filter = (*CLINICAL_FILTERS, "country", "species", "commodity")
    search_fields = ("product__brand_name",)
    autocomplete_fields = ("product",)


@admin.register(models.ClinicalNote)
class NoteAdmin(ReviewActionsMixin, SimpleHistoryAdmin):
    list_display = ("generic", "kind", "species", "review_status")
    list_filter = (*CLINICAL_FILTERS, "kind")
    autocomplete_fields = ("generic",)


@admin.register(models.Interaction)
class InteractionAdmin(ReviewActionsMixin, SimpleHistoryAdmin):
    list_display = ("generic_a", "generic_b", "severity", "review_status")
    list_filter = (*CLINICAL_FILTERS, "severity")
    autocomplete_fields = ("generic_a", "generic_b")


admin.site.register(models.Indication, search_fields=("name",))
admin.site.register(models.Route, list_display=("code", "name"))
admin.site.register(models.Commodity)
