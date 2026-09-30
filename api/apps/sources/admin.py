from django.contrib import admin

from .models import Source, SourceLink


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "publisher", "country", "publication_date")
    list_filter = ("source_type", "country")
    search_fields = ("title", "publisher", "doi", "url")


admin.site.register(SourceLink, list_display=("source", "content_type", "object_id", "locator"))
