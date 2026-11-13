from django.urls import path

from . import views

urlpatterns = [
    path("staff/ai/providers/", views.providers),
    path("staff/ai/providers/<int:pk>/", views.provider_update),
    path("staff/ai/providers/<int:pk>/test/", views.provider_test),
    path("staff/ai/routes/", views.routes),
    path("staff/ai/routes/<int:pk>/", views.route_update),
    path("staff/ai/usage/", views.usage),
    path("staff/ai/report-triage/", views.report_triage),
]
