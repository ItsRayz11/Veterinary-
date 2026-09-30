from django.urls import path

from . import views

urlpatterns = [
    path("generics/", views.GenericList.as_view()),
    path("generics/<slug:slug>/", views.generic_detail),
    path("products/<slug:slug>/", views.product_detail),
    path("companies/<slug:slug>/", views.company_detail),
    path("countries/", views.countries),
    path("species/", views.species_list),
]
