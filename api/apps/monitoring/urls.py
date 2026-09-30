from django.urls import path

from . import views

urlpatterns = [
    path("monitoring/client-errors/", views.report),
    path("staff/errors/", views.errors),
    path("staff/errors/<int:pk>/resolve/", views.resolve),
]
