from django.db import migrations


def wire(apps, schema_editor):
    """Connect the DailyMed row to its importer. It stays disabled: an admin must still confirm
    DailyMed's terms, approve the mapping and the first batch."""
    DataSource = apps.get_model("automation", "DataSource")
    DataSource.objects.filter(slug="us-dailymed-animal").update(
        importer="us-dailymed",
        data_url="https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
        "?pagesize=100&doctype=50577-6",
        regulator_name="US Food and Drug Administration, Center for Veterinary Medicine "
        "(labels published via DailyMed, US National Library of Medicine)",
        attribution_text="Source: DailyMed, US National Library of Medicine. US labelling only.",
        licence_url="https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm",
        method="api",
    )


class Migration(migrations.Migration):
    dependencies = [("automation", "0008_guard_bypass")]
    operations = [migrations.RunPython(wire, migrations.RunPython.noop)]
