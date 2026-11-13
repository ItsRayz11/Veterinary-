from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Catalog3D, CatalogPlan, FxRate, Lead, Retailer, RetailerOffer, Supplier


@admin.register(Retailer)
class RetailerAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "kind", "status", "integrates_stock")
    list_filter = ("status", "kind", "country")


@admin.register(RetailerOffer)
class OfferAdmin(SimpleHistoryAdmin):
    list_display = ("retailer", "pack", "amount", "currency", "stock_state", "status", "verified")
    list_filter = ("status", "verified", "stock_state")


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "usd_per_unit", "as_of", "source_note")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status")
    list_filter = ("status",)


@admin.register(Catalog3D)
class Catalog3DAdmin(admin.ModelAdmin):
    list_display = ("title", "supplier", "status", "rights_confirmed", "asset_size")
    list_filter = ("status",)
    exclude = ("asset",)


@admin.register(CatalogPlan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "amount", "currency", "active")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "company", "plan", "status", "created_at")
