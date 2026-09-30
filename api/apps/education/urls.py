from django.urls import path

from . import views

urlpatterns = [
    path("study/subjects/", views.subjects),
    path("study/questions/", views.questions),
    path("study/past-papers/", views.past_papers),
    path("study/questions/<int:pk>/bookmark/", views.bookmark),
    path("study/questions/<int:pk>/report/", views.report_question),
    path("study/exams/", views.create_exam),
    path("study/exams/history/", views.history),
    path("study/exams/<int:pk>/", views.exam_detail),
    path("study/exams/<int:pk>/submit/", views.submit_exam),
]
