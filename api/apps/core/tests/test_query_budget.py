"""Performance guards: public endpoints must not issue more queries as the data grows (N+1)."""

from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.clinical.models import ClinicalNote, DoseRegimen, Route
from apps.countries.models import Country
from apps.ingestion import services as ingest
from apps.pharma.models import Generic, Product, ProductRegistration
from apps.species.models import Species
from apps.units.models import Unit

# Measured on the development catalogue, with a little headroom. Raising one needs a reason.
BUDGET = {
    "/api/v1/generics/": 4,
    "/api/v1/generics/enrofloxacin/": 16,
    "/api/v1/products/dev-enro-1/": 14,
    "/api/v1/products/dev-enro-1/prices/": 4,
    "/api/v1/search/?q=enro": 6,
    "/api/v1/countries/": 3,
    "/api/v1/countries/PK/": 5,
    "/api/v1/species/": 3,
    "/api/v1/species/dog/": 6,
    "/api/v1/drug-classes/": 4,
    "/api/v1/study/subjects/": 3,
    "/api/v1/study/lessons/": 3,
    "/api/v1/listings/jobs/": 3,
}


@pytest.fixture
def catalog(db):
    call_command("seed_dev_catalog")
    return APIClient()


def count(client, url) -> int:
    with CaptureQueriesContext(connection) as q:
        assert client.get(url).status_code == 200
    return len(q)


@pytest.mark.parametrize("url", sorted(BUDGET))
def test_endpoint_stays_within_its_query_budget(catalog, url):
    assert count(catalog, url) <= BUDGET[url]


def test_generic_detail_queries_do_not_grow_with_doses_notes_and_brands(catalog):
    base = count(catalog, "/api/v1/generics/enrofloxacin/")
    generic = Generic.objects.get(slug="enrofloxacin")
    route = Route.objects.create(code="SC", name="Subcutaneous")
    unit = Unit.objects.get(code="mg/kg")
    for sp in Species.objects.all()[:8]:
        DoseRegimen.objects.create(
            generic=generic,
            species=sp,
            route=route,
            dose_unit=unit,
            dose_min=Decimal("1"),
            dose_max=Decimal("2"),
            is_development_data=True,
        )
        ClinicalNote.objects.create(
            generic=generic,
            species=sp,
            kind="warning",
            text=f"note {sp.slug}",
            is_development_data=True,
        )
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    csv_text = "brand_name,generic_name,manufacturer,registration_number\n" + "".join(
        f"Grow-{i},Enrofloxacin,Grow Pharma {i},G-{i}\n" for i in range(8)
    )
    batch = ingest.stage_batch(
        user=editor,
        country=Country.objects.get(iso2="PK"),
        source_data={"title": "Fictional", "publisher": "Test", "license_note": "Fictional data"},
        csv_text=csv_text,
    )
    ingest.approve_clean(batch, editor)
    Product.objects.filter(brand_name__startswith="Grow-").update(
        review_status="manufacturer_supplied"
    )
    ProductRegistration.objects.filter(registration_number__startswith="G-").update(
        review_status="manufacturer_supplied"
    )
    data = catalog.get("/api/v1/generics/enrofloxacin/").json()
    assert len(data["doses"]) == 8 and len(data["notes"]) == 8 and len(data["brands"]) >= 10
    assert count(catalog, "/api/v1/generics/enrofloxacin/") <= base + 2


def test_country_and_class_pages_do_not_grow_with_products(catalog):
    base_country = count(catalog, "/api/v1/countries/PK/")
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    csv_text = "brand_name,generic_name,manufacturer,registration_number\n" + "".join(
        f"Bulk-{i},Enrofloxacin,Bulk Pharma {i},B-{i}\n" for i in range(10)
    )
    batch = ingest.stage_batch(
        user=editor,
        country=Country.objects.get(iso2="PK"),
        source_data={"title": "Fictional", "publisher": "Test", "license_note": "Fictional data"},
        csv_text=csv_text,
    )
    ingest.approve_clean(batch, editor)
    Product.objects.filter(brand_name__startswith="Bulk-").update(
        review_status="manufacturer_supplied"
    )
    ProductRegistration.objects.filter(registration_number__startswith="B-").update(
        review_status="manufacturer_supplied"
    )
    page = catalog.get("/api/v1/countries/PK/").json()
    assert len([p for p in page["products"] if p["brand_name"].startswith("Bulk-")]) == 10
    assert count(catalog, "/api/v1/countries/PK/") <= base_country + 3
