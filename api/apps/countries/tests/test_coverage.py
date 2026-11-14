import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.core.models import ReviewStatus
from apps.countries.coverage import coverage_report
from apps.countries.models import Country
from apps.pharma.models import Generic, Product, ProductRegistration

pytestmark = pytest.mark.django_db


@pytest.fixture
def gb_product():
    call_command("seed_reference")
    gb = Country.objects.get(iso2="GB")
    company = Company.objects.create(
        name="Example Pharma", country=gb, review_status=ReviewStatus.OFFICIAL_REGULATORY
    )
    generic = Generic.objects.create(
        name="Albendazole", review_status=ReviewStatus.OFFICIAL_REGULATORY
    )
    product = Product.objects.create(
        brand_name="Albex",
        generic=generic,
        manufacturer=company,
        review_status=ReviewStatus.OFFICIAL_REGULATORY,
    )
    reg = ProductRegistration.objects.create(
        product=product,
        country=gb,
        registration_number="R1",
        status="registered",
        review_status=ReviewStatus.OFFICIAL_REGULATORY,
        last_checked_at=timezone.now(),
    )
    return gb, product, reg


def _flags(client):
    data = client.get("/api/v1/products/").json()
    data = data["results"] if isinstance(data, dict) else data
    return {p["slug"]: p["unverified"] for p in data}


def row(iso2="GB"):
    return next(r for r in coverage_report() if r["iso2"] == iso2)


def test_small_country_is_not_indexable_and_says_why(gb_product):
    r = row()
    assert r["registrations"] == 1 and r["indexable"] is False
    assert "1 of 300 registrations needed" in r["blockers"][0]


def test_thresholds_are_data_per_country(gb_product):
    gb, _, reg = gb_product
    gb.index_min_registrations = 1
    gb.save()
    assert row()["indexable"] is False  # registration has no feed source yet
    assert "sourced" in row()["blockers"][0]
    from apps.automation.models import DataSource

    reg.data_source = DataSource.objects.get(slug="uk-vmd-pid")
    reg.save()
    assert row()["indexable"] is True
    gb.index_mode = Country.IndexMode.NEVER
    gb.save()
    assert row()["indexable"] is False


def test_sitemap_flags_follow_country_coverage(gb_product):
    gb, product, reg = gb_product
    client = APIClient()
    flags = _flags(client)
    assert flags[product.slug] is True  # official listing in a country not ready: keep out
    gb.index_mode = Country.IndexMode.ALWAYS
    gb.save()
    cache.clear()
    flags = _flags(client)
    assert flags[product.slug] is False
    detail = client.get(f"/api/v1/products/{product.slug}/").json()
    assert detail["status"]["indexable"] is True


def test_clinically_reviewed_records_stay_indexable(gb_product):
    _, product, _ = gb_product
    Product.objects.filter(pk=product.pk).update(review_status=ReviewStatus.VERIFIED)
    detail = APIClient().get(f"/api/v1/products/{product.slug}/").json()
    assert detail["status"]["indexable"] is True


def test_countries_endpoint_and_staff_report(gb_product):
    client = APIClient()
    gb = next(c for c in client.get("/api/v1/countries/").json() if c["iso2"] == "GB")
    assert gb["indexable"] is False and gb["registrations"] == 1
    assert client.get("/api/v1/countries/GB/").json()["coverage"]["blockers"]
