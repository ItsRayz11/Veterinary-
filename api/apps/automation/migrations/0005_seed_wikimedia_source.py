"""Registers the Wikimedia Pageviews API as a trend source (disabled until an admin approves it)."""

from django.db import migrations


def add(apps, schema_editor):
    DataSource = apps.get_model("automation", "DataSource")
    DataSource.objects.get_or_create(
        slug="wikimedia-pageviews",
        defaults={
            "name": "Wikimedia Pageviews API",
            "publisher": "Wikimedia Foundation",
            "kind": "open_data",
            "landing_url": "https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews",
            "data_url": "",
            "licence_note": "Pageview data is CC0 (public domain); API terms at wikimedia.org. Confirm before use.",
            "notes": "Used only for topic trend signals in the editorial assistant. General public interest, not veterinary-specific.",
            "content_type": "page-view trends",
            "geography": "Global (English Wikipedia)",
            "method": "api",
            "robots_status": "n/a",
            "extraction_scope": "Daily view counts for named article titles only.",
            "enabled": False,
            "import_enabled": False,
            "priority": 80,
        },
    )


def remove(apps, schema_editor):
    apps.get_model("automation", "DataSource").objects.filter(slug="wikimedia-pageviews").delete()


class Migration(migrations.Migration):
    dependencies = [("automation", "0004_source_registry")]
    operations = [migrations.RunPython(add, remove)]
