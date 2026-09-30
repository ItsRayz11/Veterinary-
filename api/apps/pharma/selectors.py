"""Read queries for the pharma catalogue. Always prefetch to avoid N+1."""

from django.db.models import Prefetch

from .models import Generic, Product, ProductRegistration


def public_generic_detail(slug: str) -> Generic:
    return (
        Generic.objects.listed()
        .select_related("drug_class")
        .prefetch_related("synonyms", "ingredients")
        .get(slug=slug)
    )


def public_registrations():
    """Prefetch that only carries reviewed registrations (never leak unreviewed ones)."""
    return Prefetch(
        "registrations",
        queryset=ProductRegistration.objects.listed().select_related("country"),
    )


def brands_for_generic(generic: Generic, country_iso2: str | None = None):
    qs = (
        Product.objects.listed()
        .filter(generic=generic)
        .select_related("generic", "manufacturer", "manufacturer__country")
        .prefetch_related(public_registrations(), "packs__dosage_form", "packs__pack_size_unit")
    )
    if country_iso2:
        qs = qs.filter(
            pk__in=ProductRegistration.objects.listed()
            .filter(country__iso2=country_iso2)
            .values("product")
        )
    return qs


def products_for_company(company):
    return (
        Product.objects.listed()
        .filter(manufacturer=company)
        .select_related("generic")
        .order_by("generic__name", "brand_name")
    )
