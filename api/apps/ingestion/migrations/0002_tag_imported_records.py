"""Records created by earlier imports were stored as `needs_verification`; label them as imports.

Only rows that an import created or matched and that nobody reviewed are touched. Reviewed,
development and hand-entered records keep their status.
"""

from django.db import migrations

OLD, NEW = "needs_verification", "imported_unverified"


def tag(apps, schema_editor):
    Staged = apps.get_model("ingestion", "StagedRecord")
    targets = (
        ("matched_generic", apps.get_model("pharma", "Generic")),
        ("matched_company", apps.get_model("companies", "Company")),
        ("matched_product", apps.get_model("pharma", "Product")),
    )
    for field, model in targets:
        ids = (
            Staged.objects.filter(status="approved", **{f"{field}__isnull": False})
            .values_list(f"{field}_id", flat=True)
            .distinct()
        )
        model.objects.filter(
            pk__in=list(ids), review_status=OLD, is_development_data=False
        ).update(review_status=NEW)


def untag(apps, schema_editor):
    for app, name in (("pharma", "Generic"), ("companies", "Company"), ("pharma", "Product")):
        apps.get_model(app, name).objects.filter(review_status=NEW).update(review_status=OLD)


class Migration(migrations.Migration):
    dependencies = [
        ("ingestion", "0001_initial"),
        ("pharma", "0003_alter_generic_review_status_and_more"),
        ("companies", "0002_alter_company_review_status"),
    ]
    operations = [migrations.RunPython(tag, untag)]
