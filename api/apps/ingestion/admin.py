from django.contrib import admin

from .models import ImportBatch, StagedRecord


class StagedRecordInline(admin.TabularInline):
    model = StagedRecord
    extra = 0
    can_delete = False
    fields = ("row_number", "brand_name", "generic_name", "manufacturer_name", "status", "message")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "country", "file_name", "status", "created_at")
    readonly_fields = ("kind", "country", "source", "file_name", "checksum", "created_by")
    inlines = [StagedRecordInline]

    def has_add_permission(self, request):
        return False  # imports go through the staged, audited pipeline
