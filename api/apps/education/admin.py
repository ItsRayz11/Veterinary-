from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from apps.core.admin_mixins import ReviewActionsMixin

from . import models, services


class OptionInline(admin.TabularInline):
    model = models.Option
    extra = 4
    max_num = 6


@admin.action(description="Check selected questions are publishable (options + one answer)")
def check_ready(modeladmin, request, queryset):
    for q in queryset:
        try:
            services.validate_question_ready(q)
        except ValidationError as exc:
            modeladmin.message_user(request, f"#{q.pk}: {exc.messages[0]}", messages.ERROR)


@admin.register(models.Question)
class QuestionAdmin(ReviewActionsMixin, admin.ModelAdmin):
    list_display = ("stem", "topic", "difficulty", "university", "year", "review_status")
    list_filter = (
        "review_status",
        "topic__subject",
        "difficulty",
        "country",
        "is_development_data",
    )
    search_fields = ("stem", "exam", "university")
    inlines = [OptionInline]
    actions = [check_ready, *ReviewActionsMixin.actions]


@admin.register(models.QuestionReport)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("question", "message", "resolved", "created_at")
    list_filter = ("resolved",)


admin.site.register(models.Subject)
admin.site.register(
    models.Topic, list_display=("name", "subject", "generic"), search_fields=("name",)
)
admin.site.register(models.PastPaper, list_display=("university", "course", "year", "is_published"))
