from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.core.schema import untyped_schema
from apps.countries.models import Country
from apps.pharma.models import Product, ProductPack

from . import analytics, selectors
from .models import PriceRecord, PriceSubmission, PriceType, SubmissionKind


class SubmitThrottle(UserRateThrottle):
    scope = "submit"


def _record(r: PriceRecord) -> dict:
    return {
        "id": r.pk,
        "pack": f"{r.pack.dosage_form.name} {r.pack.pack_size_value.normalize():f}"
        f" {r.pack.pack_size_unit.code}",
        "pack_id": r.pack_id,
        "country": r.country.iso2,
        "region": r.region,
        "city": r.city,
        "currency": r.currency,
        "price_type": r.price_type,
        "amount": str(r.amount),
        "origin": r.origin,
        "source": {"title": r.source.title, "url": r.source.url} if r.source else None,
        "observed_on": r.observed_on,
        "last_verified": r.verified_at,
    }


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def product_prices(request, slug):
    product = get_object_or_404(Product.objects.public(), slug=slug)
    records = list(selectors.price_history(product, request.query_params.get("country")))
    return Response(
        {
            "current": [_record(r) for r in selectors.current_prices(records)],
            "history": [_record(r) for r in records],
            "analytics": {
                "series": analytics.price_series(records),
                "region_comparison": analytics.region_comparison(records),
            },
            "note": "Prices are indicative, may vary by location and change without notice.",
        }
    )


class SubmissionSerializer(serializers.ModelSerializer):
    country = serializers.SlugRelatedField(
        slug_field="iso2", queryset=Country.objects.filter(is_active=True)
    )

    class Meta:
        model = PriceSubmission
        fields = (
            "kind",
            "pack",
            "country",
            "region",
            "city",
            "currency",
            "price_type",
            "amount",
            "target",
            "note",
            "evidence_url",
        )

    def validate(self, attrs):
        if attrs["kind"] == SubmissionKind.NEW_PRICE:
            if not attrs.get("amount") or attrs["amount"] <= 0:
                raise serializers.ValidationError({"amount": "A positive price is required."})
            if attrs.get("price_type") not in PriceType.values:
                raise serializers.ValidationError({"price_type": "Choose a price type."})
        elif not attrs.get("target"):
            raise serializers.ValidationError({"target": "Choose the price you are reporting."})
        elif attrs["target"].pack_id != attrs["pack"].pk:
            raise serializers.ValidationError({"target": "Price does not belong to this pack."})
        return attrs


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SubmitThrottle])
def submit(request):
    """Submit an updated price or report an incorrect one. Enters moderation; not shown publicly."""
    s = SubmissionSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    sub = s.save(submitted_by=request.user)
    return Response({"id": sub.pk, "status": sub.status}, status=status.HTTP_201_CREATED)


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def pack_choices(request, slug):
    """Packs of a product for the submission form."""
    product = get_object_or_404(Product.objects.public(), slug=slug)
    packs = ProductPack.objects.filter(product=product).select_related(
        "dosage_form", "pack_size_unit"
    )
    return Response(
        [
            {
                "id": p.pk,
                "label": f"{p.dosage_form.name} {p.pack_size_value.normalize():f} "
                f"{p.pack_size_unit.code}",
            }
            for p in packs
        ]
    )
