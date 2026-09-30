from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.pharma.urls")),
    path("api/v1/", include("apps.search.urls")),
    path("api/v1/", include("apps.pricing.urls")),
    path("api/v1/", include("apps.education.urls")),
    path("api/v1/", include("apps.staff.urls")),
    path("api/v1/", include("apps.ingestion.urls")),
    path("api/v1/", include("apps.opportunities.urls")),
    path("api/v1/", include("apps.automation.urls")),
    path("api/v1/", include("apps.assistant.urls")),
    path("api/v1/", include("apps.monitoring.urls")),
    path("api/v1/", include("apps.push.urls")),
    path("api/v1/", include("apps.calculators.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]
