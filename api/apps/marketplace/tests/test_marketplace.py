import base64
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.countries.models import Country
from apps.marketplace.models import (
    Catalog3D,
    FxRate,
    Retailer,
    RetailerOffer,
    Supplier,
    validate_glb,
)
from apps.marketplace.views import convert
from apps.pharma.models import Product, ProductPack


def api(role, name=None):
    u, _ = User.objects.get_or_create(username=name or f"u-{role}", defaults={"role": role})
    c = APIClient()
    c.force_login(u)
    return c, u


def glb(size_extra=0):
    json_chunk = b"{}  "
    body = len(json_chunk).to_bytes(4, "little") + b"JSON" + json_chunk
    total = 12 + len(body)
    return b"glTF" + (2).to_bytes(4, "little") + total.to_bytes(4, "little") + body


@pytest.fixture
def setup(db):
    call_command("seed_dev_catalog")
    product = Product.objects.get(slug="dev-enro-1")
    pk = Country.objects.get(iso2="PK")
    r = Retailer.objects.create(name="Vet Mart", country=pk, kind="online", status="approved")
    return product, ProductPack.objects.get(product=product), r


def test_glb_validation():
    validate_glb(glb())
    for bad in (
        b"",
        b"glTF",
        b"NOPE" + glb()[4:],
        glb()[:-1],
        b"glTF" + (1).to_bytes(4, "little") + glb()[8:],
    ):
        with pytest.raises(ValidationError):
            validate_glb(bad)
    with pytest.raises(ValidationError):
        validate_glb(glb() + b"0" * (9 * 1024 * 1024))


@pytest.mark.django_db
def test_offer_never_claims_stock_without_a_recent_check(setup):
    _, pack, r = setup
    o = RetailerOffer(
        retailer=r,
        pack=pack,
        amount=Decimal("10"),
        currency="PKR",
        price_observed_on=date.today(),
        stock_state="in_stock",
    )
    with pytest.raises(ValidationError):
        o.full_clean()  # in stock but no check time
    o.stock_checked_at = timezone.now()
    o.full_clean()
    o.save()
    assert o.effective_stock == "in_stock"
    o.stock_checked_at = timezone.now() - timedelta(days=30)
    assert o.effective_stock == "unknown"


@pytest.mark.django_db
def test_public_offers_only_show_approved_verified_and_retailer_approved(setup):
    product, pack, r = setup
    RetailerOffer.objects.create(
        retailer=r,
        pack=pack,
        amount=Decimal("10"),
        currency="PKR",
        price_observed_on=date.today(),
        status="approved",
        verified=False,
    )
    url = f"/api/v1/products/{product.slug}/offers/?country=PK"
    assert APIClient().get(url).json()["results"] == []
    RetailerOffer.objects.update(verified=True)
    res = APIClient().get(url).json()["results"]
    assert len(res) == 1 and res[0]["stock"] == "unknown"
    Retailer.objects.update(status="paused")
    assert APIClient().get(url).json()["results"] == []


def test_fx_conversion_is_indicative_and_absent_without_rates():
    usd = FxRate(currency="USD", usd_per_unit=Decimal("1"), as_of=timezone.now(), source_note="x")
    pkr = FxRate(
        currency="PKR", usd_per_unit=Decimal("0.0036"), as_of=timezone.now(), source_note="x"
    )
    rates = {"USD": usd, "PKR": pkr}
    value, as_of = convert(Decimal("1000"), "PKR", "USD", rates)
    assert value == Decimal("3.60") and as_of
    assert convert(Decimal("5"), "PKR", "EUR", rates) == (None, None)
    assert convert(Decimal("5"), "PKR", "PKR", rates) == (Decimal("5"), None)


@pytest.mark.django_db
def test_admin_only_manages_fx_and_moderators_manage_retailers(setup):
    mod, _ = api(Role.MODERATOR)
    assert mod.get("/api/v1/staff/fx-rates/").status_code == 403
    assert mod.get("/api/v1/staff/retailers/").status_code == 200
    adm, _ = api(Role.ADMIN)
    r = adm.post(
        "/api/v1/staff/fx-rates/",
        {
            "currency": "usd",
            "usd_per_unit": "1",
            "as_of": timezone.now().isoformat(),
            "source_note": "Manual",
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    assert APIClient().get("/api/v1/staff/offers/").status_code in (401, 403)


@pytest.mark.django_db
def test_supplier_upload_flow_requires_approval_validation_and_moderation(setup):
    sup, user = api(Role.COMPANY_REP)
    assert sup.post("/api/v1/my/catalogs-3d/", {}, format="json").status_code == 403
    assert sup.post("/api/v1/my/supplier/", {"name": "Acme 3D"}, format="json").status_code == 200
    Supplier.objects.update(status="approved")
    body = {
        "title": "Syringe",
        "rights_confirmed": True,
        "asset_base64": base64.b64encode(b"not a glb").decode(),
    }
    assert sup.post("/api/v1/my/catalogs-3d/", body, format="json").status_code == 400
    body["asset_base64"] = base64.b64encode(glb()).decode()
    r = sup.post("/api/v1/my/catalogs-3d/", body, format="json")
    assert r.status_code == 201 and r.json()["status"] == "pending"
    pk = r.json()["id"]
    assert APIClient().get("/api/v1/catalogs-3d/").json()["results"] == []
    assert APIClient().get(f"/api/v1/catalogs-3d/{pk}/asset/").status_code == 404
    mod, _ = api(Role.MODERATOR)
    assert (
        mod.patch(
            f"/api/v1/staff/catalogs-3d/{pk}/", {"status": "approved"}, format="json"
        ).status_code
        == 200
    )
    assert len(APIClient().get("/api/v1/catalogs-3d/").json()["results"]) == 1
    asset = APIClient().get(f"/api/v1/catalogs-3d/{pk}/asset/")
    assert asset.status_code == 200 and asset["Content-Type"] == "model/gltf-binary"
    assert asset["X-Content-Type-Options"] == "nosniff"
    Catalog3D.objects.filter(pk=pk).update(rights_confirmed=False)
    assert (
        mod.patch(
            f"/api/v1/staff/catalogs-3d/{pk}/", {"status": "approved"}, format="json"
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_payments_are_off_and_leads_are_the_only_path():
    from apps.marketplace.models import CatalogPlan

    CatalogPlan.objects.create(
        name="Starter", kind="listing", amount=Decimal("10"), currency="USD", active=True
    )
    plans = APIClient().get("/api/v1/catalog-plans/").json()
    assert plans["payments_enabled"] is False and len(plans["results"]) == 1
    r = APIClient().post(
        "/api/v1/catalog-leads/",
        {"name": "A", "email": "a@b.org", "plan": plans["results"][0]["id"]},
        format="json",
    )
    assert r.status_code == 201
    assert (
        APIClient()
        .post("/api/v1/catalog-leads/", {"name": "A", "email": "bad"}, format="json")
        .status_code
        == 400
    )
    assert APIClient().get("/api/v1/staff/leads/").status_code in (401, 403)
