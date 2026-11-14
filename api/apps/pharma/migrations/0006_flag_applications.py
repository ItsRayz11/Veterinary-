from django.db import migrations

MARKER = "This is an application, not a registration."


def flag_applications(apps, schema_editor):
    """DRAP's public lists contain applications for registration, not approvals; mark them so
    they can never be presented as registered products."""
    Product = apps.get_model("pharma", "Product")
    Product.objects.filter(description__contains=MARKER, listing_kind="unspecified").update(
        listing_kind="application"
    )


class Migration(migrations.Migration):
    dependencies = [("pharma", "0005_publication_tiers")]
    operations = [migrations.RunPython(flag_applications, migrations.RunPython.noop)]
