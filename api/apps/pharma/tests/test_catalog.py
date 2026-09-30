import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.companies.models import Company
from apps.core.models import ReviewStatus
from apps.countries.models import Country
from apps.pharma import selectors
from apps.pharma.models import Generic, Product
from apps.units.models import Unit


@pytest.fixture
def catalog(db):
    call_command("seed_dev_catalog")
    return Generic.objects.get(slug="enrofloxacin")


def test_generic_has_many_brands_from_different_companies(catalog):
    brands = selectors.brands_for_generic(catalog)
    assert brands.count() == 2
    assert len({b.manufacturer_id for b in brands}) == 2


def test_seed_is_idempotent(catalog):
    call_command("seed_dev_catalog")
    assert Product.objects.count() == 2 and Company.objects.count() == 2


def test_country_filter(catalog):
    assert selectors.brands_for_generic(catalog, "PK").count() == 2
    assert selectors.brands_for_generic(catalog, "IN").count() == 0


def test_dev_data_hidden_when_flag_off(catalog, settings):
    settings.SHOW_DEVELOPMENT_DATA = False
    assert Generic.objects.public().count() == 0
    settings.SHOW_DEVELOPMENT_DATA = True
    assert Generic.objects.public().count() == 1


def test_dev_data_cannot_be_verified(catalog):
    catalog.review_status = ReviewStatus.VERIFIED
    with pytest.raises(IntegrityError), transaction.atomic():
        catalog.save()


def test_duplicate_brand_same_company_blocked(catalog):
    p = Product.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(
            brand_name="dev-enro  1 ", generic=catalog, manufacturer=p.manufacturer
        )


def test_same_brand_name_different_company_allowed(catalog):
    other = Company.objects.create(name="Other Co", country=Country.objects.get(iso2="IN"))
    Product.objects.create(brand_name="DEV-Enro 1", generic=catalog, manufacturer=other)


def test_unit_conversion(db):
    call_command("seed_reference")
    mg, g, ml = Unit.objects.get(code="mg"), Unit.objects.get(code="g"), Unit.objects.get(code="mL")
    assert mg.convert(1000, g) == 1
    with pytest.raises(ValueError):
        mg.convert(1, ml)


def test_generic_detail_query_count(catalog, django_assert_max_num_queries):
    with django_assert_max_num_queries(9):
        g = selectors.public_generic_detail("enrofloxacin")
        rows = [
            (b.brand_name, b.manufacturer.name, [r.country.iso2 for r in b.registrations.all()])
            for b in selectors.brands_for_generic(g)
        ]
    assert len(rows) == 2
