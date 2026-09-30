from django.urls import path

from . import views

urlpatterns = [
    path("staff/summary/", views.summary),
    path("staff/review-queue/", views.review_queue),
    path("staff/review-queue/<str:model_key>/<int:pk>/status/", views.set_status),
    path("staff/review-queue/<str:model_key>/<int:pk>/history/", views.record_history),
    path("staff/price-submissions/", views.price_submissions),
    path("staff/price-submissions/<int:pk>/<str:decision>/", views.moderate_submission),
    path("staff/question-reports/", views.question_reports),
    path("staff/question-reports/<int:pk>/resolve/", views.resolve_question_report),
    path("staff/audit-log/", views.audit_log),
    path("staff/automation/", views.automation_status),
    path("staff/automation/run/<str:task>/", views.automation_run),
]
