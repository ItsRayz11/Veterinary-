from .models import PriceRecord


def price_history(product, country_iso2: str | None = None):
    """Published prices for all packs of a product, newest first; grouped by the caller."""
    qs = (
        PriceRecord.objects.published()
        .filter(pack__product=product)
        .select_related("pack__dosage_form", "pack__pack_size_unit", "country", "source")
    )
    if country_iso2:
        qs = qs.filter(country__iso2=country_iso2)
    return qs


def current_prices(records):
    """Latest record per (pack, country, region, city, price_type) from a newest-first list."""
    seen, out = set(), []
    for r in records:
        key = (r.pack_id, r.country_id, r.region, r.city, r.price_type)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out
