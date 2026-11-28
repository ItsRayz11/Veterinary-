from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.countries.models import Country
from apps.pharma.models import Product, ProductPack
from apps.pricing.models import (
    PriceOrigin,
    PriceRecord,
    PriceSubmission,
    SubmissionKind,
    SubmissionStatus,
)
from apps.pricing.services import screen_submission
from apps.sources.models import Source


@pytest.fixture
def s(db):
    call_command("seed_dev_catalog")
    product = Product.objects.get(slug="dev-enro-1")
    return {
        "pack": ProductPack.objects.get(product=product),
        "pk": Country.objects.get(iso2="PK"),
        "source": Source.objects.create(source_type="other", title="List", url="https://e.org"),
        "user": User.objects.create_user("buyer", password="x"),
    }


def published(s, amount, currency="PKR", price_type="retail", is_published=True):
    PriceRecord.objects.create(
        pack=s["pack"],
        country=s["pk"],
        currency=currency,
        price_type=price_type,
        amount=Decimal(amount),
        origin=PriceOrigin.EDITORIAL,
        source=s["source"],
        observed_on=date(2026, 11, 1),
        is_published=is_published,
    )


def submit(s, amount, price_type="retail"):
    return PriceSubmission.objects.create(
        kind=SubmissionKind.NEW_PRICE,
        pack=s["pack"],
        country=s["pk"],
        currency="PKR",
        price_type=price_type,
        amount=Decimal(amount),
        submitted_by=s["user"],
    )


def test_far_off_price_is_flagged_against_the_median_of_published_prices(s):
    for a in ("100", "110", "120"):
        published(s, a)
    assert screen_submission(submit(s, "115")) == {
        "references": 3,
        "median": "110.00",
        "outlier": False,
    }
    assert screen_submission(submit(s, "900"))["outlier"] is True
    assert screen_submission(submit(s, "10"))["outlier"] is True


def test_only_comparable_published_prices_count(s):
    published(s, "100")
    published(s, "100", currency="USD")
    published(s, "100", price_type="wholesale")
    published(s, "100", is_published=False)
    out = screen_submission(submit(s, "900"))
    assert out["references"] == 1 and out["outlier"] is False  # too few to judge


def test_moderators_see_the_screening_and_nothing_is_decided_for_them(s):
    for a in ("100", "110", "120"):
        published(s, a)
    sub = submit(s, "900")
    client = APIClient()
    client.force_authenticate(User.objects.create_user("mod", password="x", role=Role.MODERATOR))
    row = client.get("/api/v1/staff/price-submissions/").json()["results"][0]
    assert row["screening"]["outlier"] is True and row["screening"]["median"] == "110.00"
    sub.refresh_from_db()
    assert sub.status == SubmissionStatus.PENDING
