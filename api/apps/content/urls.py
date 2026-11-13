from django.urls import path

from . import views

urlpatterns = [
    path("articles/", views.article_list),
    path("articles/submit/", views.article_submit),
    path("articles/<slug:slug>/", views.article_detail),
    path("staff/articles/", views.articles),
    path("staff/articles/suggest-topics/", views.suggest_topics),
    path("staff/articles/<int:pk>/", views.article_update),
    path("staff/articles/<int:pk>/<str:action>/", views.article_action),
    path("staff/topics/", views.topics),
    path("staff/topics/<int:pk>/", views.topic_update),
    path("staff/topics/<int:pk>/draft/", views.draft_from_topic),
]
