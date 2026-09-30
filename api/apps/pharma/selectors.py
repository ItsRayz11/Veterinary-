"""Read queries for the pharma catalogue. Always prefetch to avoid N+1."""

from .models import Generic, Product


def public_generic_detail(slug: str) -> Generic:
    return (
        Generic.objects.public()
        .select_related("drug_class")
        .prefetch_related("synonyms", "ingredients")
        .get(slug=slug)
    )


def brands_for_generic(generic: Generic, country_iso2: str | None = None):
    qs = (
        Product.objects.public()
        .filter(generic=generic)
        .select_related("manufacturer", "manufacturer__country")
        .prefetch_related("registrations__country", "packs__dosage_form", "packs__pack_size_unit")
    )
    if country_iso2:
        qs = qs.filter(registrations__country__iso2=country_iso2).distinct()
    return qs


def products_for_company(company):
    return (
        Product.objects.public()
        .filter(manufacturer=company)
        .select_related("generic")
        .order_by("generic__name", "brand_name")
    )
