from django.contrib import admin

from .models import Article, ArticleRevision, TopicSuggestion


class RevisionInline(admin.TabularInline):
    model = ArticleRevision
    extra = 0
    can_delete = False
    readonly_fields = ("number", "title", "body", "edited_by", "at")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "author", "medical", "ai_assisted", "publish_at")
    list_filter = ("status", "medical", "ai_assisted")
    search_fields = ("title", "body")
    inlines = [RevisionInline]


@admin.register(TopicSuggestion)
class TopicSuggestionAdmin(admin.ModelAdmin):
    list_display = ("title", "basis", "status")
    list_filter = ("basis", "status")
