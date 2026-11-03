from django.urls import path

from . import views

urlpatterns = [
    path("universities/", views.UniversityList.as_view()),
    path("universities/<slug:slug>/", views.university_detail),
]
