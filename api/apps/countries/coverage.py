"""Country coverage controls: a country's pages are indexable by search engines only when its
public collection is big and well-sourced enough. Thresholds live on the Country row (data, not
code), so no country is special-cased. Pages stay reachable for visitors either way."""

from django.core.cache import cache
from django.db.models import Count, Q

from apps.core.models import PUBLIC_STATUSES

from .models import Country

CACHE_KEY = "country-indexable-ids"
CACHE_SECONDS = 300


def coverage_report() -> list[dict]:
    from apps.pharma.models import ProductRegistration

    public = [s.value for s in PUBLIC_STATUSES]
    counts = {
        row["country"]: row
        for row in ProductRegistration.objects.filter(
            review_status__in=public, product__is_development_data=False
        )
        .values("country")
        .annotate(
            total=Count("pk"),
            sourced=Count("pk", filter=Q(data_source__isnull=False, last_checked_at__isnull=False)),
            products=Count("product", distinct=True),
        )
    }
    out = []
    for c in Country.objects.filter(is_active=True):
        row = counts.get(c.pk, {"total": 0, "sourced": 0, "products": 0})
        pct = round(100 * row["sourced"] / row["total"]) if row["total"] else 0
        reasons = []
        if row["total"] < c.index_min_registrations:
            reasons.append(f"{row['total']} of {c.index_min_registrations} registrations needed")
        if pct < c.index_min_provenance_pct:
            reasons.append(f"{pct}% sourced, {c.index_min_provenance_pct}% needed")
        if c.index_mode == Country.IndexMode.NEVER:
            indexable, reasons = False, ["indexing switched off by an admin"]
        elif c.index_mode == Country.IndexMode.ALWAYS:
            indexable = True
        else:
            indexable = not reasons
        out.append(
            {
                "iso2": c.iso2,
                "name": c.name,
                "mode": c.index_mode,
                "registrations": row["total"],
                "products": row["products"],
                "sourced_pct": pct,
                "min_registrations": c.index_min_registrations,
                "min_sourced_pct": c.index_min_provenance_pct,
                "indexable": indexable,
                "blockers": reasons,
            }
        )
    return out


def indexable_country_ids() -> frozenset[int]:
    ids = cache.get(CACHE_KEY)
    if ids is None:
        wanted = {r["iso2"] for r in coverage_report() if r["indexable"]}
        ids = frozenset(Country.objects.filter(iso2__in=wanted).values_list("pk", flat=True))
        cache.set(CACHE_KEY, ids, CACHE_SECONDS)
    return ids
