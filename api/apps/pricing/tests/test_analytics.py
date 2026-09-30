from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.countries.models import Country
from apps.pharma.models import Product, ProductPack
from apps.pricing import analytics
from apps.pricing.models import PriceOrigin, PriceRecord
from apps.pricing.selectors import price_history
from apps.sources.models import Source


@pytest.fixture
def setup(db):
    call_command("seed_dev_catalog")
    product = Product.objects.get(slug="dev-enro-1")
    return {
        "product": product,
        "pack": ProductPack.objects.get(product=product),
        "pk": Country.objects.get(iso2="PK"),
        "source": Source.objects.create(source_type="other", title="List", url="https://e.org"),
    }


def add(s, amount, day, region="", currency="PKR", price_type="retail", published=True):
    return PriceRecord.objects.create(
        pack=s["pack"],
        country=s["pk"],
        region=region,
        currency=currency,
        price_type=price_type,
        amount=Decimal(amount),
        origin=PriceOrigin.EDITORIAL,
        source=s["source"],
        observed_on=day,
        is_published=published,
    )


def records(s):
    return list(price_history(s["product"]))


def test_change_and_percent_are_exact_and_rounded_half_up(setup):
    add(setup, "300", date(2026, 1, 1))
    add(setup, "350", date(2026, 3, 1))
    [series] = analytics.price_series(records(setup))
    assert series["latest"] == "350.00" and series["direction"] == "up"
    assert series["change"] == "50.00" and series["change_percent"] == "16.67"
    assert (series["min"], series["max"]) == ("300.00", "350.00")
    assert [p["date"] for p in series["points"]] == [date(2026, 1, 1), date(2026, 3, 1)]


def test_decrease_same_and_single_observation(setup):
    add(setup, "200", date(2026, 1, 1))
    add(setup, "150", date(2026, 2, 1))
    [down] = analytics.price_series(records(setup))
    assert down["direction"] == "down" and down["change_percent"] == "-25.00"
    PriceRecord.objects.all().delete()
    add(setup, "100", date(2026, 1, 1))
    [single] = analytics.price_series(records(setup))
    assert single["direction"] == "none" and single["change"] is None
    add(setup, "100", date(2026, 2, 1))
    [same] = analytics.price_series(records(setup))
    assert same["direction"] == "same" and same["change_percent"] == "0.00"


def test_currencies_types_and_locations_never_mix(setup):
    add(setup, "100", date(2026, 1, 1))
    add(setup, "9", date(2026, 1, 1), currency="USD")
    add(setup, "80", date(2026, 1, 1), price_type="distributor")
    add(setup, "110", date(2026, 1, 1), region="Punjab")
    series = analytics.price_series(records(setup))
    assert len(series) == 4
    assert all(s["change"] is None for s in series)


def test_unpublished_prices_are_excluded(setup):
    add(setup, "100", date(2026, 1, 1))
    add(setup, "999", date(2026, 2, 1), published=False)
    [series] = analytics.price_series(records(setup))
    assert series["latest"] == "100.00"


def test_region_comparison_uses_latest_per_region_and_needs_two_regions(setup):
    add(setup, "100", date(2026, 1, 1), region="Punjab")
    assert analytics.region_comparison(records(setup)) == []
    add(setup, "120", date(2026, 1, 1), region="Sindh")
    add(setup, "110", date(2026, 2, 1), region="Punjab")  # newer Punjab price wins
    add(setup, "5", date(2026, 2, 1), region="KP", currency="USD")  # other currency ignored
    [cmp] = analytics.region_comparison(records(setup))
    assert [r["region"] for r in cmp["regions"]] == ["Punjab", "Sindh"]
    assert cmp["regions"][0]["amount"] == "110.00"
    assert cmp["spread"] == "10.00" and cmp["spread_percent"] == "9.09"


def test_endpoint_includes_analytics(setup):
    add(setup, "300", date(2026, 1, 1))
    add(setup, "330", date(2026, 2, 1))
    data = APIClient().get("/api/v1/products/dev-enro-1/prices/").json()
    assert data["analytics"]["series"][0]["change_percent"] == "10.00"
    assert data["analytics"]["region_comparison"] == []
