from django.urls import path

from . import views

urlpatterns = [
    path("interactions/check/", views.interaction_check),
    path("assistant/ask/", views.ask),
]
