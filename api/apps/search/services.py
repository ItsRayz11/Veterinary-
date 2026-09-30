"""Global search across generics, brands and companies.

Case-insensitive, accent-insensitive (via normalised columns), synonym-aware, with a small
typo-tolerant fallback. This is the SQLite-safe baseline; on Postgres it is replaced by
pg_trgm/FTS behind the same `search()` interface (see docs/ARCHITECTURE.md).
"""

from difflib import get_close_matches

from apps.companies.models import Company
from apps.core.text import normalize_name
from apps.pharma.models import Generic, GenericSynonym, Product

LIMIT = 8
MIN_QUERY = 2


def _rank(name: str, q: str) -> int:
    n = normalize_name(name)
    return 0 if n == q else 1 if n.startswith(q) else 2


def _generics(q: str):
    direct = list(Generic.objects.public().filter(normalized_name__contains=q))
    via_syn = list(
        Generic.objects.public().filter(
            pk__in=GenericSynonym.objects.filter(normalized_synonym__contains=q).values("generic")
        )
    )
    seen, out = set(), []
    for g in direct + via_syn:
        if g.pk not in seen:
            seen.add(g.pk)
            out.append(g)
    return sorted(out, key=lambda g: (_rank(g.name, q), g.name))[:LIMIT]


def _fuzzy_generics(q: str):
    names = {g.normalized_name: g for g in Generic.objects.public()}
    for syn in GenericSynonym.objects.filter(generic__in=Generic.objects.public()).select_related(
        "generic"
    ):
        names[syn.normalized_synonym] = syn.generic
    close = get_close_matches(q, names.keys(), n=LIMIT, cutoff=0.75)
    seen, out = set(), []
    for c in close:
        g = names[c]
        if g.pk not in seen:
            seen.add(g.pk)
            out.append(g)
    return out


def search(query: str) -> dict:
    q = normalize_name(query)
    empty = {"query": query, "generics": [], "products": [], "companies": [], "did_you_mean": []}
    if len(q) < MIN_QUERY:
        return empty
    generics = _generics(q)
    products = list(
        Product.objects.public()
        .filter(normalized_brand_name__contains=q)
        .select_related("generic", "manufacturer")
        .order_by("brand_name")[:LIMIT]
    )
    companies = list(
        Company.objects.public().filter(normalized_name__contains=q).order_by("name")[:LIMIT]
    )
    did_you_mean = []
    if not (generics or products or companies):
        did_you_mean = [g.name for g in _fuzzy_generics(q)]
    return {
        "query": query,
        "generics": [{"name": g.name, "slug": g.slug} for g in generics],
        "products": [
            {
                "name": p.brand_name,
                "slug": p.slug,
                "generic": p.generic.name,
                "manufacturer": p.manufacturer.name,
            }
            for p in products
        ],
        "companies": [{"name": c.name, "slug": c.slug} for c in companies],
        "did_you_mean": did_you_mean,
    }
