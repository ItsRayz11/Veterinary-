from django.urls import path

from . import browse, views

urlpatterns = [
    path("generics/", views.GenericList.as_view()),
    path("generics/<slug:slug>/", views.generic_detail),
    path("products/<slug:slug>/", views.product_detail),
    path("companies/<slug:slug>/", views.company_detail),
    path("countries/", views.countries),
    path("species/", views.species_list),
    path("species/<slug:slug>/", browse.species_detail),
    path("drug-classes/", browse.drug_class_list),
    path("drug-classes/<slug:slug>/", browse.drug_class_detail),
    path("countries/<str:iso2>/", browse.country_detail),
]
