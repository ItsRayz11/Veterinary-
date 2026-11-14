from django.db import migrations

# Facts only. Nothing is approved here: terms, field mapping and the first batch stay unapproved.
DEFAULTS = {
    "uk-vmd-pid": {
        "regulator_name": "Veterinary Medicines Directorate (VMD), UK",
        "attribution_text": "Contains public sector information licensed under the "
        "Open Government Licence v3.0. Source: Veterinary Medicines Directorate.",
        "licence_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "licence_note": "Open Government Licence v3.0: 'All content is available under the OGL "
        "v3.0, except where otherwise stated' (VMD page, checked 2026-11-14). Attribution required.",
    },
    "ca-health-canada-dpd": {
        "regulator_name": "Health Canada, Veterinary Drugs Directorate",
        "attribution_text": "Contains information licensed under the Open Government Licence "
        "– Canada. Source: Health Canada Drug Product Database.",
        "licence_url": "https://open.canada.ca/en/open-government-licence-canada",
        "licence_note": "Open Government Licence - Canada v2.0, stated on the dataset page "
        "(checked 2026-11-14). Monthly updates.",
    },
}


def fill(apps, schema_editor):
    DataSource = apps.get_model("automation", "DataSource")
    for slug, values in DEFAULTS.items():
        DataSource.objects.filter(slug=slug).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0006_publication_tiers"),
        ("pharma", "0006_flag_applications"),
    ]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
