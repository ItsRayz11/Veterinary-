"""Browse endpoints: species, drug classes and country landing pages (reviewed data only)."""

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.clinical.models import DoseRegimen
from apps.core.models import ReviewStatus
from apps.core.schema import untyped_schema
from apps.countries.models import Country
from apps.species.models import Species

from . import selectors
from .models import DrugClass, Generic, Product, ProductRegistration, RegistrationSpecies
from .serializers import GenericListSerializer, ProductBriefSerializer


def _descendant_ids(model, root) -> list[int]:
    """The node and everything below it (trees here are shallow)."""
    ids, frontier = [root.pk], [root.pk]
    while frontier:
        frontier = list(model.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
        ids.extend(frontier)
    return ids


def authorized_medicines(species_ids: list[int]) -> list[dict]:
    """Medicines whose regulator-stated target species include this species (or a child of it).

    Built from individual authorisations (product + country), never from the ingredient alone.
    Shows reviewed registrations and, labelled, unreviewed imported ones (same rule as listings).
    """
    registrations = ProductRegistration.objects.listed().filter(
        pk__in=RegistrationSpecies.objects.filter(species_id__in=species_ids).values("registration")
    )
    rows = registrations.values_list(
        "product__generic__slug",
        "product__generic__name",
        "product__generic__drug_class__name",
        "country__iso2",
        "review_status",
        "status",
    )
    by_generic: dict[str, dict] = {}
    for slug, name, cls, iso2, review, status in rows:
        g = by_generic.setdefault(
            slug,
            {
                "slug": slug,
                "name": name,
                "drug_class": cls,
                "authorizations": 0,
                "countries": set(),
                "unverified": False,
                "in_force": 0,
            },
        )
        g["authorizations"] += 1
        g["countries"].add(iso2)
        g["unverified"] = g["unverified"] or review == ReviewStatus.IMPORTED_UNVERIFIED
        g["in_force"] += status == "registered"
    return [
        {**g, "countries": sorted(g["countries"])}
        for g in sorted(by_generic.values(), key=lambda g: g["name"].lower())
    ]


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def species_detail(request, slug):
    species = get_object_or_404(Species.objects.select_related("parent"), slug=slug)
    ids = _descendant_ids(Species, species)
    doses = DoseRegimen.objects.listed().filter(species_id__in=ids, product__isnull=True)
    dose_counts = dict(doses.values_list("generic").annotate(n=Count("pk")))
    generics = (
        Generic.objects.listed()
        .filter(pk__in=dose_counts)
        .select_related("drug_class")
        .order_by("name")
    )
    return Response(
        {
            "authorized_medicines": authorized_medicines(ids),
            "slug": species.slug,
            "name": species.name,
            "is_food_producing": species.is_food_producing,
            "parent": {"slug": species.parent.slug, "name": species.parent.name}
            if species.parent
            else None,
            "children": [{"slug": c.slug, "name": c.name} for c in species.children.all()],
            "generics": [
                {**GenericListSerializer(g).data, "dose_count": dose_counts[g.pk]} for g in generics
            ],
        }
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def drug_class_list(request):
    direct = dict(
        Generic.objects.listed()
        .exclude(drug_class__isnull=True)
        .values_list("drug_class")
        .annotate(n=Count("pk"))
        .values_list("drug_class", "n")
    )
    classes = list(DrugClass.objects.select_related("parent"))
    children: dict[int | None, list[int]] = {}
    for c in classes:
        children.setdefault(c.parent_id, []).append(c.pk)
    totals: dict[int, int] = {}

    def total(pk: int) -> int:
        """Generics in this class and everything below it, matching what the detail page lists."""
        if pk not in totals:
            totals[pk] = direct.get(pk, 0) + sum(total(k) for k in children.get(pk, []))
        return totals[pk]

    return Response(
        [
            {
                "slug": c.slug,
                "name": c.name,
                "parent": c.parent.slug if c.parent else None,
                "generic_count": total(c.pk),
            }
            for c in classes
        ]
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def drug_class_detail(request, slug):
    cls = get_object_or_404(DrugClass.objects.select_related("parent"), slug=slug)
    ancestors, node = [], cls.parent
    while node is not None:
        ancestors.insert(0, {"slug": node.slug, "name": node.name})
        node = node.parent
    generics = (
        Generic.objects.listed()
        .filter(drug_class_id__in=_descendant_ids(DrugClass, cls))
        .select_related("drug_class")
        .order_by("name")
    )
    return Response(
        {
            "slug": cls.slug,
            "name": cls.name,
            "ancestors": ancestors,
            "children": [{"slug": c.slug, "name": c.name} for c in cls.children.all()],
            "generics": GenericListSerializer(generics, many=True).data,
        }
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def country_detail(request, iso2):
    country = get_object_or_404(Country, iso2=iso2.upper(), is_active=True)
    registered = ProductRegistration.objects.listed().filter(country=country).values("product")
    products = (
        Product.objects.listed()
        .filter(
            Q(pk__in=registered)
            | Q(
                review_status=ReviewStatus.IMPORTED_UNVERIFIED,
                manufacturer__country=country,
            )
        )
        .select_related("generic", "manufacturer__country")
        .prefetch_related(selectors.public_registrations())
        .order_by("generic__name", "brand_name")
    )
    return Response(
        {
            "iso2": country.iso2,
            "name": country.name,
            "currency": country.currency_code,
            "regulator": country.regulator_name,
            "products": ProductBriefSerializer(products, many=True).data,
        }
    )
