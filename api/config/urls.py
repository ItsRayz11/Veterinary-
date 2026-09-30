from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.pharma.urls")),
    path("api/v1/", include("apps.search.urls")),
    path("api/v1/", include("apps.pricing.urls")),
    path("api/v1/", include("apps.calculators.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]
