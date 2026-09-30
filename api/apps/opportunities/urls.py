from django.urls import path

from . import views

urlpatterns = [
    path("staff/listings/", views.staff_listings),
    path("staff/listings/<str:kind>/<int:pk>/<str:decision>/", views.staff_decide),
    path("listings/<str:kind>/", views.listings),
    path("listings/<str:kind>/submit/", views.submit),
    path("listings/<str:kind>/<int:pk>/", views.listing_detail),
    path("listings/<str:kind>/<int:pk>/report/", views.report),
]
