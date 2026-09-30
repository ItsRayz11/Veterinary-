from django.urls import path

from . import views

urlpatterns = [
    path("products/<slug:slug>/prices/", views.product_prices),
    path("products/<slug:slug>/packs/", views.pack_choices),
    path("prices/submissions/", views.submit),
]
