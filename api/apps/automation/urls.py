from django.urls import path

from . import views

urlpatterns = [path("cron/<str:task>/", views.cron)]
