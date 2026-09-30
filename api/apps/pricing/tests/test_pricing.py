from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.countries.models import Country
from apps.pharma.models import Product, ProductPack
from apps.pricing import services
from apps.pricing.models import PriceOrigin, PriceRecord, PriceSubmission
from apps.sources.models import Source


@pytest.fixture
def setup(db):
    call_command("seed_dev_catalog")
    product = Product.objects.get(slug="dev-enro-1")
    return {
        "product": product,
        "pack": ProductPack.objects.get(product=product),
        "pk": Country.objects.get(iso2="PK"),
    }


def source():
    return Source.objects.create(source_type="other", title="Price list", url="https://example.org")


def make_price(s, amount, day, **kw):
    fields = dict(
        pack=s["pack"],
        country=s["pk"],
        currency="PKR",
        price_type="retail",
        amount=Decimal(amount),
        origin=PriceOrigin.EDITORIAL,
        source=source(),
        observed_on=day,
        is_published=True,
    )
    fields.update(kw)
    return PriceRecord.objects.create(**fields)


def user(name, role=Role.REGISTERED):
    return User.objects.create_user(name, password="x", role=role)


def test_price_needs_source_unless_user_submitted(setup):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_price(setup, "100", date(2026, 1, 1), source=None)
    make_price(setup, "100", date(2026, 1, 1), source=None, origin=PriceOrigin.USER_SUBMITTED)


def test_price_must_be_positive_and_is_append_only(setup):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_price(setup, "0", date(2026, 1, 1))
    p = make_price(setup, "100", date(2026, 1, 1))
    p.amount = Decimal("999")
    with pytest.raises(ValueError):
        p.save()


def test_history_and_current(setup):
    make_price(setup, "100", date(2026, 1, 1))
    make_price(setup, "120", date(2026, 6, 1))
    make_price(setup, "150", date(2026, 9, 1), is_published=False)  # unpublished: hidden
    body = APIClient().get("/api/v1/products/dev-enro-1/prices/").json()
    assert [h["amount"] for h in body["history"]] == ["120.00", "100.00"]
    assert [c["amount"] for c in body["current"]] == ["120.00"]
    assert body["current"][0]["source"]["title"] == "Price list"


def test_submission_requires_login_and_is_hidden_until_approved(setup):
    api = APIClient()
    payload = {
        "kind": "new_price",
        "pack": setup["pack"].pk,
        "country": setup["pk"].pk,
        "price_type": "retail",
        "amount": "555.00",
        "currency": "PKR",
    }
    assert api.post("/api/v1/prices/submissions/", payload, format="json").status_code in (401, 403)
    api.force_authenticate(user("u1"))
    r = api.post("/api/v1/prices/submissions/", payload, format="json")
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert APIClient().get("/api/v1/products/dev-enro-1/prices/").json()["history"] == []


def test_invalid_submissions_rejected(setup):
    api = APIClient()
    api.force_authenticate(user("u2"))
    base = {"pack": setup["pack"].pk, "country": setup["pk"].pk}
    assert (
        api.post(
            "/api/v1/prices/submissions/",
            {**base, "kind": "new_price", "amount": "-5", "price_type": "retail"},
            format="json",
        ).status_code
        == 400
    )
    assert (
        api.post(
            "/api/v1/prices/submissions/",
            {**base, "kind": "new_price", "amount": "5"},
            format="json",
        ).status_code
        == 400
    )
    assert (
        api.post(
            "/api/v1/prices/submissions/", {**base, "kind": "report_incorrect"}, format="json"
        ).status_code
        == 400
    )


def test_moderator_approves_new_price(setup):
    sub = PriceSubmission.objects.create(
        kind="new_price",
        pack=setup["pack"],
        country=setup["pk"],
        price_type="retail",
        amount=Decimal("555"),
        submitted_by=user("u3"),
    )
    with pytest.raises(PermissionDenied):
        services.approve_submission(sub, user("nobody"))
    services.approve_submission(sub, user("mod", Role.MODERATOR))
    rec = PriceRecord.objects.get()
    assert rec.origin == PriceOrigin.USER_SUBMITTED and rec.is_published and rec.currency == "PKR"
    assert Decimal(str(rec.confidence)) < 1
    with pytest.raises(ValidationError):
        services.approve_submission(sub, user("mod2", Role.MODERATOR))


def test_moderator_cannot_approve_own_submission(setup):
    mod = user("mod", Role.MODERATOR)
    sub = PriceSubmission.objects.create(
        kind="new_price",
        pack=setup["pack"],
        country=setup["pk"],
        price_type="retail",
        amount=Decimal("5"),
        submitted_by=mod,
    )
    with pytest.raises(PermissionDenied):
        services.approve_submission(sub, mod)


def test_accepted_report_unpublishes_price_but_keeps_history_row(setup):
    price = make_price(setup, "100", date(2026, 1, 1))
    sub = PriceSubmission.objects.create(
        kind="report_incorrect",
        pack=setup["pack"],
        country=setup["pk"],
        target=price,
        note="Wrong",
        submitted_by=user("u4"),
    )
    services.approve_submission(sub, user("mod", Role.MODERATOR))
    price.refresh_from_db()
    assert price.is_published is False and PriceRecord.objects.count() == 1


def test_reject_requires_reason(setup):
    sub = PriceSubmission.objects.create(
        kind="new_price",
        pack=setup["pack"],
        country=setup["pk"],
        price_type="retail",
        amount=Decimal("5"),
        submitted_by=user("u5"),
    )
    with pytest.raises(ValidationError):
        services.reject_submission(sub, user("mod", Role.MODERATOR), "")
    services.reject_submission(sub, user("mod3", Role.MODERATOR), "Not credible")
    sub.refresh_from_db()
    assert sub.status == "rejected"
