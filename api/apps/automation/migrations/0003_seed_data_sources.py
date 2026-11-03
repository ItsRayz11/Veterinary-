"""Registers the external data sources researched in docs/DATA_RESOURCES.md.

Rows are plain data (not imported from app code, so later code changes cannot alter history).
All start with the scheduled check on, import off, and terms unconfirmed: a person confirms each
publisher's terms in the admin before any import can run.
"""

from django.db import migrations

SOURCES = [
    {
        "slug": "uk-vmd-pid",
        "name": "UK VMD Product Information Database",
        "publisher": "Veterinary Medicines Directorate (UK)",
        "country_iso2": "GB",
        "kind": "regulator_list",
        "landing_url": "https://www.vmd.defra.gov.uk/ProductInformationDatabase/",
        "data_url": "https://www.vmd.defra.gov.uk/ProductInformationDatabase/downloads/VMD_ProductInformationDatabase.xml",
        "licence_note": "Open Government Licence v3.0 (stated on the VMD site). Attribution required.",
        "importer": "uk-vmd",
        "notes": "Snapshot XML of authorised products. No strengths or withdrawal periods in the file (only in linked SPC PDFs).",
    },
    {
        "slug": "ca-health-canada-dpd",
        "name": "Health Canada Drug Product Database (veterinary)",
        "publisher": "Health Canada",
        "country_iso2": "CA",
        "kind": "open_data",
        "landing_url": "https://open.canada.ca/data/en/dataset/bf55e42a-63cb-4556-bfd8-44f26e5a36fe",
        "data_url": "https://open.canada.ca/data/dataset/bf55e42a-63cb-4556-bfd8-44f26e5a36fe/resource/b05ae610-0366-478f-993f-b4afbdaadbc6/download/allfiles.zip",
        "licence_note": "Open Government Licence - Canada (reported by secondary sources; confirm on the dataset page).",
        "importer": "ca-dpd",
        "notes": "Zip of header-less files for human, veterinary and disinfectant products; only class Veterinary is used.",
    },
    {
        "slug": "us-fda-green-book",
        "name": "FDA Green Book (approved animal drug products)",
        "publisher": "US FDA Center for Veterinary Medicine",
        "country_iso2": "US",
        "kind": "regulator_list",
        "landing_url": "https://www.fda.gov/animal-veterinary/products/approved-animal-drug-products-green-book",
        "licence_note": "US federal publication; confirm reuse terms on the FDA page.",
        "notes": "Updated monthly. Monitor only: no importer written yet.",
    },
    {
        "slug": "us-openfda-animal-events",
        "name": "openFDA animal and veterinary adverse events",
        "publisher": "US FDA (openFDA)",
        "country_iso2": "US",
        "kind": "open_data",
        "landing_url": "https://open.fda.gov/apis/animalandveterinary/event",
        "data_url": "https://api.fda.gov/animalandveterinary/event.json?limit=1",
        "licence_note": "CC0 per openFDA licence page (dated 2014; re-check).",
        "notes": "Reports lag 3-6 months. Signals only, never dosing guidance. Monitor only.",
    },
    {
        "slug": "us-dailymed-animal",
        "name": "DailyMed animal drug labels",
        "publisher": "US National Library of Medicine",
        "country_iso2": "US",
        "kind": "open_data",
        "landing_url": "https://dailymed.nlm.nih.gov/dailymed/spl-resources.cfm",
        "licence_note": "Public-domain status not confirmed; check the DailyMed policy page.",
        "notes": "Manufacturer label text: import as manufacturer-supplied, never verified. Monitor only.",
    },
    {
        "slug": "au-apvma-pubcris",
        "name": "APVMA PubCRIS (registered veterinary products)",
        "publisher": "Australian Pesticides and Veterinary Medicines Authority",
        "country_iso2": "AU",
        "kind": "open_data",
        "landing_url": "https://data.gov.au/data/dataset/apvma-pubcris-dataset-for-registered-agricultural-and-veterinary-chemical-products-and-approved-acti",
        "licence_note": "CC BY 3.0 AU (attribution required).",
        "notes": "Weekly CSV/JSON/XML and API. The portal returned 403 to a script during research; a 403 here is expected until access is arranged.",
    },
    {
        "slug": "pk-drap-registry",
        "name": "DRAP registered products search",
        "publisher": "Drug Regulatory Authority of Pakistan",
        "country_iso2": "PK",
        "kind": "portal",
        "landing_url": "https://eapp.dra.gov.pk/WebProductIndex.php",
        "licence_note": "Registry disclaimer says it must not be used for research, citation or statistics: get DRAP permission first.",
        "notes": "Monitor only.",
    },
    {
        "slug": "pk-drap-applications",
        "name": "DRAP applications of registration (veterinary)",
        "publisher": "Drug Regulatory Authority of Pakistan",
        "country_iso2": "PK",
        "kind": "regulator_list",
        "landing_url": "https://www.dra.gov.pk/?p=31571",
        "licence_note": "Public lists; terms not individually confirmed. Applications are not registrations.",
        "notes": "The 420 + 102 applications were imported earlier from these lists (hidden, unreviewed).",
    },
    {
        "slug": "in-cdsco-vet-list",
        "name": "CDSCO approved veterinary drugs list",
        "publisher": "CDSCO (India)",
        "country_iso2": "IN",
        "kind": "document",
        "landing_url": "https://www.cdsco.gov.in/opencms/opencms/en/Home/",
        "data_url": "https://www.cdsco.gov.in/opencms/export/sites/CDSCO_WEB/Pdf-documents/Veterinary-Drug-Data-30.06.2026.pdf",
        "licence_note": "Public government list; terms not confirmed.",
        "notes": "PDF tables: needs a person to download and a PDF adapter before import. Was unreachable from the dev machine.",
    },
    {
        "slug": "eu-ema-upd",
        "name": "EMA Union Product Database (veterinary)",
        "publisher": "European Medicines Agency",
        "country_iso2": "",
        "kind": "portal",
        "landing_url": "https://www.ema.europa.eu/en/veterinary-regulatory-overview/veterinary-medicinal-products-regulation/union-product-database",
        "licence_note": "No bulk-download or reuse licence found; see the UPD access policy.",
        "notes": "Monitor only.",
    },
    {
        "slug": "farad",
        "name": "FARAD (withdrawal interval guidance)",
        "publisher": "Food Animal Residue Avoidance Databank (USDA-funded)",
        "country_iso2": "US",
        "kind": "portal",
        "landing_url": "https://www.farad.org/",
        "licence_note": "No reuse terms found: link out, do not copy.",
        "notes": "Monitor only.",
    },
]


def seed(apps, schema_editor):
    DataSource = apps.get_model("automation", "DataSource")
    for row in SOURCES:
        DataSource.objects.get_or_create(
            slug=row["slug"],
            defaults={
                **row,
                "enabled": True,
                "import_enabled": False,
                "data_url": row.get("data_url", ""),
            },
        )


def unseed(apps, schema_editor):
    apps.get_model("automation", "DataSource").objects.filter(
        slug__in=[r["slug"] for r in SOURCES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("automation", "0002_datasource")]
    operations = [migrations.RunPython(seed, unseed)]
