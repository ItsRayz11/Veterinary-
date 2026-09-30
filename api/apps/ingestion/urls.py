from django.urls import path

from . import views

urlpatterns = [
    path("staff/imports/", views.batches),
    path("staff/imports/<int:pk>/", views.batch_detail),
    path("staff/imports/<int:pk>/approve-clean/", views.approve_all_clean),
    path("staff/imports/<int:pk>/rows/<int:row_pk>/<str:decision>/", views.resolve_row),
]
