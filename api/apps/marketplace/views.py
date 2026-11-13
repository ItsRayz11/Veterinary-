import base64
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole, IsModerator
from apps.core.crud import crud_views, simple_row
from apps.core.models import AuditLog
from apps.core.schema import untyped_schema
from apps.core.throttling import ClientIPMixin, UserThrottle
from apps.pharma.models import Product
from apps.pricing import selectors

from .models import (
    ApprovalStatus,
    Catalog3D,
    CatalogPlan,
    FxRate,
    Lead,
    Retailer,
    RetailerOffer,
    StockState,
    Supplier,
    validate_glb,
)


class IsAdminRole(HasRole):
    roles = frozenset({Role.ADMIN})


class LeadThrottle(ClientIPMixin, AnonRateThrottle):
    scope = "submit"


class SubmitThrottle(UserThrottle):
    scope = "submit"


def _pack_label(p) -> str:
    return f"{p.dosage_form.name} {p.pack_size_value.normalize():f} {p.pack_size_unit.code}"


# ---------- public: offers and comparison ----------


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def product_offers(request, slug):
    product = get_object_or_404(Product.objects.listed(), slug=slug)
    qs = RetailerOffer.objects.filter(
        pack__product=product,
        status=ApprovalStatus.APPROVED,
        verified=True,
        retailer__status=ApprovalStatus.APPROVED,
    ).select_related("retailer__country", "pack__dosage_form", "pack__pack_size_unit")
    if c := request.query_params.get("country"):
        qs = qs.filter(retailer__country__iso2=c.upper())
    return Response(
        {
            "results": [
                {
                    "retailer": o.retailer.name,
                    "kind": o.retailer.kind,
                    "city": o.retailer.city,
                    "country": o.retailer.country.iso2,
                    "pack": _pack_label(o.pack),
                    "amount": str(o.amount),
                    "currency": o.currency,
                    "price_date": o.price_observed_on,
                    "stock": o.effective_stock,
                    "stock_label": StockState(o.effective_stock).label,
                    "stock_checked_at": o.stock_checked_at,
                    "listing_url": o.listing_url,
                    "note": o.tax_shipping_note,
                }
                for o in qs[:100]
            ],
            "note": (
                "Offers are listed by participating retailers. Stock is shown only when the "
                "retailer or VetRef staff confirmed it recently; otherwise it is Unknown. "
                "VetRef does not sell these products and has no checkout."
            ),
        }
    )


def convert(amount: Decimal, src: str, dst: str, rates: dict[str, FxRate]):
    """Indicative conversion through the USD rates admins entered. None if either is missing."""
    if src == dst:
        return amount, None
    a, b = rates.get(src), rates.get(dst)
    if not a or not b:
        return None, None
    value = (amount * a.usd_per_unit / b.usd_per_unit).quantize(Decimal("0.01"))
    return value, min(a.as_of, b.as_of)


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def price_comparison(request, slug):
    """Like-for-like by pack, per country, in local currency; optional indicative conversion."""
    product = get_object_or_404(Product.objects.listed(), slug=slug)
    target = (request.query_params.get("currency") or "").upper()
    rates = {r.currency: r for r in FxRate.objects.all()}
    records = selectors.current_prices(list(selectors.price_history(product)))
    packs: dict[int, dict] = {}
    for r in records:
        grp = packs.setdefault(
            r.pack_id,
            {"pack": _pack_label(r.pack), "unit": r.pack.pack_size_unit.code, "rows": []},
        )
        conv, as_of = (None, None)
        if target:
            conv, as_of = convert(r.amount, r.currency, target, rates)
        grp["rows"].append(
            {
                "country": r.country.iso2,
                "price_type": r.price_type,
                "amount": str(r.amount),
                "currency": r.currency,
                "per_unit": str((r.amount / r.pack.pack_size_value).quantize(Decimal("0.0001"))),
                "observed_on": r.observed_on,
                "source": {"title": r.source.title, "url": r.source.url} if r.source else None,
                "converted": str(conv) if conv is not None else None,
                "converted_currency": target if conv is not None else None,
                "fx_as_of": as_of,
            }
        )
    return Response(
        {
            "packs": list(packs.values()),
            "note": (
                "Compare the same pack only. Converted amounts are indicative, use the exchange "
                "rate shown with its date, and exclude tax, shipping and local price rules."
            ),
            "currencies": sorted(rates),
        }
    )


# ---------- public: 3D catalogs ----------


def _catalog_row(c: Catalog3D, *, detail=False) -> dict:
    d = {
        "id": c.pk,
        "title": c.title,
        "description": c.description,
        "collection": c.collection,
        "supplier": c.supplier.name,
        "product": c.product.slug if c.product_id else None,
        "fallback_image": c.fallback_image_path,
        "has_model": bool(c.asset_size),
        "asset_url": f"/api/v1/catalogs-3d/{c.pk}/asset/" if c.asset_size else None,
    }
    return d


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def catalog_list(request):
    qs = (
        Catalog3D.objects.filter(
            status=ApprovalStatus.APPROVED, supplier__status=ApprovalStatus.APPROVED
        )
        .select_related("supplier", "product")
        .defer("asset")
    )
    return Response({"results": [_catalog_row(c) for c in qs[:100]]})


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def catalog_asset(request, pk):
    c = get_object_or_404(
        Catalog3D.objects.filter(
            status=ApprovalStatus.APPROVED, supplier__status=ApprovalStatus.APPROVED
        ),
        pk=pk,
    )
    if not c.asset_size:
        return Response({"detail": "No model."}, status=http.HTTP_404_NOT_FOUND)
    resp = HttpResponse(bytes(c.asset), content_type="model/gltf-binary")
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Disposition"] = f'inline; filename="catalog-{c.pk}.glb"'
    resp["Cache-Control"] = "public, max-age=3600"
    return resp


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def plan_list(request):
    return Response(
        {
            "results": [
                {"id": p.pk, "name": p.name, "kind": p.kind, "amount": str(p.amount),
                 "currency": p.currency, "description": p.description}
                for p in CatalogPlan.objects.filter(active=True)
            ],
            "payments_enabled": False,
            "note": "Online payment is not active yet. Send an enquiry and we will contact you.",
        }
    )  # fmt: skip


@untyped_schema
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LeadThrottle])
def lead_create(request):
    d = request.data
    plan = CatalogPlan.objects.filter(pk=d.get("plan") or 0, active=True).first()
    lead = Lead(
        name=str(d.get("name", ""))[:120], email=str(d.get("email", ""))[:254],
        company=str(d.get("company", ""))[:160], message=str(d.get("message", ""))[:1000],
        plan=plan,
    )  # fmt: skip
    try:
        lead.full_clean()
    except ValidationError as exc:
        return Response({"detail": "; ".join(exc.messages)}, status=http.HTTP_400_BAD_REQUEST)
    lead.save()
    return Response({"detail": "Thank you. We will be in touch."}, status=201)


# ---------- supplier self-service ----------


@untyped_schema
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_supplier(request):
    s = Supplier.objects.filter(owner=request.user).first()
    if request.method == "POST" and s is None:
        s = Supplier(
            owner=request.user, name=str(request.data.get("name", ""))[:160],
            description=str(request.data.get("description", ""))[:2000],
            website=str(request.data.get("website", ""))[:200],
        )  # fmt: skip
        try:
            s.full_clean()
        except ValidationError as exc:
            return Response({"detail": "; ".join(exc.messages)}, status=400)
        s.save()
    if s is None:
        return Response({"supplier": None})
    return Response({"supplier": {"id": s.pk, "name": s.name, "status": s.status}})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SubmitThrottle])
def my_catalog_upload(request):
    """JSON body with the GLB as base64 (keeps uploads inside the existing JSON API)."""
    s = Supplier.objects.filter(owner=request.user).first()
    if s is None or s.status != ApprovalStatus.APPROVED:
        return Response({"detail": "Your supplier profile must be approved first."}, status=403)
    d = request.data
    c = Catalog3D(
        supplier=s, title=str(d.get("title", ""))[:160],
        description=str(d.get("description", ""))[:2000],
        collection=str(d.get("collection", ""))[:100],
        fallback_image_path=str(d.get("fallback_image_path", ""))[:200],
        rights_confirmed=bool(d.get("rights_confirmed")),
    )  # fmt: skip
    try:
        raw = base64.b64decode(str(d.get("asset_base64", "")), validate=True)
        validate_glb(raw)
        c.full_clean(exclude=["asset"])
    except (ValueError, ValidationError) as exc:
        msg = "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Invalid upload."
        return Response({"detail": msg}, status=http.HTTP_400_BAD_REQUEST)
    c.asset, c.asset_size = raw, len(raw)
    c.save()  # status stays pending until staff approve it
    return Response({"id": c.pk, "status": c.status}, status=201)


# ---------- staff ----------


RETAILER_FIELDS = ["name", "country", "city", "kind", "website", "status", "integrates_stock"]
retailers, retailer_update = crud_views(
    Retailer, fields=RETAILER_FIELDS, perm=IsModerator, name="retailer",
    row=simple_row(RETAILER_FIELDS, lambda r: {"country_iso2": r.country.iso2}),
)  # fmt: skip

OFFER_FIELDS = [
    "retailer", "pack", "amount", "currency", "price_observed_on", "stock_state",
    "stock_checked_at", "listing_url", "tax_shipping_note", "status", "verified",
]  # fmt: skip
offers, offer_update = crud_views(
    RetailerOffer, fields=OFFER_FIELDS, perm=IsModerator, name="offer",
    row=simple_row(
        OFFER_FIELDS,
        lambda o: {"retailer_name": o.retailer.name, "pack_label": _pack_label(o.pack),
                   "effective_stock": o.effective_stock},
    ),
    queryset=lambda: RetailerOffer.objects.select_related(
        "retailer", "pack__dosage_form", "pack__pack_size_unit"
    ),
)  # fmt: skip

FX_FIELDS = ["currency", "usd_per_unit", "as_of", "source_note"]
fx_rates, fx_update = crud_views(
    FxRate, fields=FX_FIELDS, perm=IsAdminRole, name="fx_rate", row=simple_row(FX_FIELDS),
)  # fmt: skip

PLAN_FIELDS = ["name", "kind", "amount", "currency", "description", "active"]
plans, plan_update = crud_views(
    CatalogPlan, fields=PLAN_FIELDS, perm=IsAdminRole, name="catalog_plan",
    row=simple_row(PLAN_FIELDS),
)  # fmt: skip

SUPPLIER_FIELDS = ["name", "description", "website", "status"]
suppliers, supplier_update = crud_views(
    Supplier, fields=SUPPLIER_FIELDS, perm=IsModerator, name="supplier",
    row=simple_row(SUPPLIER_FIELDS, lambda s: {"owner": s.owner.username}),
    queryset=lambda: Supplier.objects.select_related("owner"),
)  # fmt: skip

CATALOG_FIELDS = [
    "title", "description", "collection", "fallback_image_path", "rights_confirmed", "status",
    "reject_reason",
]  # fmt: skip
catalogs, catalog_update = crud_views(
    Catalog3D, fields=CATALOG_FIELDS, perm=IsModerator, name="catalog3d",
    row=simple_row(
        CATALOG_FIELDS,
        lambda c: {"supplier_name": c.supplier.name, "asset_size": c.asset_size},
    ),
    queryset=lambda: Catalog3D.objects.select_related("supplier").defer("asset"),
)  # fmt: skip


@untyped_schema
@api_view(["GET"])
@permission_classes([IsModerator])
def leads(request):
    return Response(
        {
            "results": [
                {"id": ld.pk, "name": ld.name, "email": ld.email, "company": ld.company,
                 "plan": ld.plan.name if ld.plan else "", "message": ld.message,
                 "status": ld.status, "created_at": ld.created_at}
                for ld in Lead.objects.select_related("plan")[:200]
            ]
        }
    )  # fmt: skip


@untyped_schema
@api_view(["POST"])
@permission_classes([IsModerator])
def lead_status(request, pk, action):
    ld = get_object_or_404(Lead, pk=pk)
    if action not in ("contacted", "closed"):
        return Response({"detail": "Unknown action."}, status=404)
    ld.status = action
    ld.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        actor=request.user, action=f"lead_{action}", object_type=ld._meta.label,
        object_id=str(ld.pk),
    )  # fmt: skip
    return Response({"id": ld.pk, "status": ld.status, "at": timezone.now()})
