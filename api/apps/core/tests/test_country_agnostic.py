"""Guards the rule 'no country-specific hardcoding': behaviour comes from data, not ISO literals."""

import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.countries.models import Country
from apps.ingestion import services as ingest
from apps.pharma.models import Product, ProductPack, ProductRegistration
from apps.pricing import services as price_services
from apps.pricing.models import PriceSubmission

REPO = Path(__file__).resolve().parents[4]
LITERAL = re.compile(r"""["'](PK|IN)["']|\b(Pakistan|India|PKR|INR)\b""")
# Data/seed modules may name countries; everything else must stay country-agnostic.
ALLOWED = {"reference_data.py", "seed_dev_catalog.py", "seed_reference.py"}


def _source_files():
    roots = [(REPO / "api" / "apps", "*.py"), (REPO / "web" / "src", "*.ts*")]
    for root, pattern in roots:
        if not root.exists():
            continue
        for path in root.rglob(pattern):
            parts = set(path.parts)
            if parts & {"tests", "migrations", "node_modules"} or path.name in ALLOWED:
                continue
            if path.name.startswith("test_") or ".test." in path.name:
                continue
            yield path


def test_no_country_literals_in_application_code():
    offenders = []
    for path in _source_files():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if LITERAL.search(line) and not line.lstrip().startswith(("#", "//", '"""', "*")):
                offenders.append(f"{path.relative_to(REPO)}:{n}: {line.strip()[:80]}")
    assert offenders == [], "Country literals found:\n" + "\n".join(offenders)


@pytest.fixture
def world(db):
    call_command("seed_dev_catalog")  # also loads reference data (all countries)
    return {
        "editor": User.objects.create_user("ed", password="x", role=Role.EDITOR),
        "mod": User.objects.create_user("mod", password="x", role=Role.MODERATOR),
        "author": User.objects.create_user("auth", password="x"),
    }


SOURCE = {
    "title": "Fictional regulator export",
    "publisher": "Test",
    "license_note": "Fictional data for tests",
}


@pytest.mark.parametrize("iso2", ["PK", "IN", "US"])
def test_import_registration_country_page_and_price_currency_work_for_any_country(world, iso2):
    country = Country.objects.get(iso2=iso2)
    csv_text = (
        "brand_name,generic_name,manufacturer,registration_number\n"
        f"Parity-{iso2},Enrofloxacin,Parity Pharma {iso2},REG-{iso2}\n"
    )
    batch = ingest.stage_batch(
        user=world["editor"], country=country, source_data=SOURCE, csv_text=csv_text
    )
    ingest.approve_clean(batch, world["editor"])
    product = Product.objects.get(brand_name=f"Parity-{iso2}")
    assert product.manufacturer.country == country
    reg = ProductRegistration.objects.get(product=product)
    assert reg.country == country

    # publish through the data path (not the governed workflow: this test is about country logic)
    Product.objects.filter(pk=product.pk).update(review_status="manufacturer_supplied")
    ProductRegistration.objects.filter(pk=reg.pk).update(review_status="manufacturer_supplied")
    page = APIClient().get(f"/api/v1/countries/{iso2.lower()}/").json()
    assert f"Parity-{iso2}" in [p["brand_name"] for p in page["products"]]
    other = "IN" if iso2 == "PK" else "PK"
    assert all(
        p["brand_name"] != f"Parity-{iso2}"
        for p in APIClient().get(f"/api/v1/countries/{other}/").json()["products"]
    )

    pack = ProductPack.objects.filter(product__slug="dev-enro-1").first()
    sub = PriceSubmission.objects.create(
        kind="new_price",
        pack=pack,
        country=country,
        price_type="retail",
        amount=Decimal("42"),
        submitted_by=world["author"],
    )
    record = price_services.approve_submission(sub, world["mod"])
    assert record.currency == country.currency_code  # currency comes from the country row
