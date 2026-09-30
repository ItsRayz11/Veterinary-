from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.clinical.models import ClinicalNote, DoseRegimen, WithdrawalPeriod
from apps.companies.models import Company
from apps.core.text import normalize_name
from apps.countries.models import Country
from apps.sources.models import sources_for
from apps.sources.selectors import sources_map
from apps.species.models import Species

from . import selectors
from .models import Generic, Product
from .serializers import (
    CompanyBriefSerializer,
    DoseSerializer,
    GenericDetailSerializer,
    GenericListSerializer,
    NoteSerializer,
    ProductBriefSerializer,
    WithdrawalSerializer,
    _status,
    source_payload,
)


class GenericList(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = GenericListSerializer

    def get_queryset(self):
        qs = Generic.objects.public().select_related("drug_class")
        q = normalize_name(self.request.query_params.get("q", ""))
        if q:
            qs = qs.filter(normalized_name__contains=q)
        return qs


@api_view(["GET"])
@permission_classes([AllowAny])
def generic_detail(request, slug):
    generic = get_object_or_404(
        Generic.objects.public()
        .select_related("drug_class")
        .prefetch_related("synonyms", "ingredients"),
        slug=slug,
    )
    country = request.query_params.get("country") or None
    species = request.query_params.get("species") or None

    doses = list(
        DoseRegimen.objects.public()
        .filter(generic=generic, product__isnull=True)
        .select_related(
            "species", "indication", "route", "dose_unit", "max_single_dose_unit", "country"
        )
        .order_by("species__sort_order", "indication__name")
    )
    if species:
        doses = [d for d in doses if d.species.slug == species]
    notes = list(ClinicalNote.objects.public().filter(generic=generic).select_related("species"))
    brands = selectors.brands_for_generic(generic, country)

    ctx = {"sources": sources_map(doses), "note_sources": sources_map(notes)}
    return Response(
        {
            **GenericDetailSerializer(generic).data,
            "sources": source_payload([(s, "") for s in sources_for(generic)]),
            "doses": DoseSerializer(doses, many=True, context=ctx).data,
            "notes": NoteSerializer(notes, many=True, context=ctx).data,
            "brands": ProductBriefSerializer(brands, many=True).data,
            "disclaimer": (
                "Reference for licensed veterinary professionals. Not a substitute for clinical "
                "judgement or the product label."
            ),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.public()
        .select_related("generic", "manufacturer__country", "marketing_holder")
        .prefetch_related(
            "ingredients__ingredient",
            "ingredients__strength_unit",
            "ingredients__per_unit",
            "packs__dosage_form",
            "packs__pack_size_unit",
            selectors.public_registrations(),
        ),
        slug=slug,
    )
    withdrawals = (
        WithdrawalPeriod.objects.public()
        .filter(product=product)
        .select_related("product", "country", "species", "commodity", "route")
    )
    return Response(
        {
            **ProductBriefSerializer(product).data,
            "category": product.category,
            "description": product.description,
            "is_biologic": product.is_biologic,
            "marketing_holder": product.marketing_holder.name if product.marketing_holder else None,
            "ingredients": [
                {
                    "name": pi.ingredient.name,
                    "strength": f"{pi.strength_value.normalize():f}",
                    "unit": pi.strength_unit.code,
                    "per": pi.per_unit.code if pi.per_unit else None,
                    "per_value": f"{pi.per_value.normalize():f}",
                }
                for pi in product.ingredients.all()
            ],
            "packs": [
                {
                    "form": p.dosage_form.name,
                    "size": f"{p.pack_size_value.normalize():f}",
                    "unit": p.pack_size_unit.code,
                }
                for p in product.packs.all()
            ],
            "registrations": [
                {
                    "country": r.country.iso2,
                    "number": r.registration_number,
                    "status": r.status,
                    "record_status": _status(r),
                }
                for r in product.registrations.all()
            ],
            "withdrawal_periods": WithdrawalSerializer(withdrawals, many=True).data,
            "sources": source_payload([(s, "") for s in sources_for(product)]),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def company_detail(request, slug):
    company = get_object_or_404(Company.objects.public().select_related("country"), slug=slug)
    products = (
        selectors.products_for_company(company)
        .select_related("manufacturer__country")
        .prefetch_related(selectors.public_registrations())
    )
    return Response(
        {
            **CompanyBriefSerializer(company).data,
            "website": company.website,
            "description": company.description,
            "roles": [
                r
                for r, on in (
                    ("manufacturer", company.is_manufacturer),
                    ("importer", company.is_importer),
                    ("distributor", company.is_distributor),
                )
                if on
            ],
            "verified_profile": company.is_verified_profile,
            "status": _status(company),
            "products": ProductBriefSerializer(products, many=True).data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def countries(request):
    rows = Country.objects.filter(is_active=True)
    return Response(
        [
            {"iso2": c.iso2, "slug": c.slug, "name": c.name, "currency": c.currency_code}
            for c in rows
        ]
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def species_list(request):
    return Response(
        [
            {"slug": s.slug, "name": s.name, "parent": s.parent.slug if s.parent else None}
            for s in Species.objects.select_related("parent")
        ]
    )
