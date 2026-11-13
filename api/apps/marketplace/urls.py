from django.urls import path

from . import views

urlpatterns = [
    path("products/<slug:slug>/offers/", views.product_offers),
    path("products/<slug:slug>/price-comparison/", views.price_comparison),
    path("catalogs-3d/", views.catalog_list),
    path("catalogs-3d/<int:pk>/asset/", views.catalog_asset),
    path("catalog-plans/", views.plan_list),
    path("catalog-leads/", views.lead_create),
    path("my/supplier/", views.my_supplier),
    path("my/catalogs-3d/", views.my_catalog_upload),
    path("staff/retailers/", views.retailers),
    path("staff/retailers/<int:pk>/", views.retailer_update),
    path("staff/offers/", views.offers),
    path("staff/offers/<int:pk>/", views.offer_update),
    path("staff/fx-rates/", views.fx_rates),
    path("staff/fx-rates/<int:pk>/", views.fx_update),
    path("staff/catalog-plans/", views.plans),
    path("staff/catalog-plans/<int:pk>/", views.plan_update),
    path("staff/suppliers/", views.suppliers),
    path("staff/suppliers/<int:pk>/", views.supplier_update),
    path("staff/catalogs-3d/", views.catalogs),
    path("staff/catalogs-3d/<int:pk>/", views.catalog_update),
    path("staff/leads/", views.leads),
    path("staff/leads/<int:pk>/<str:action>/", views.lead_status),
]
