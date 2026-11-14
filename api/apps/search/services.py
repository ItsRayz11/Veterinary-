"""Global search across generics, brands and companies.

Case-insensitive, accent-insensitive (via normalised columns), synonym-aware, with a small
typo-tolerant fallback: pg_trgm similarity on Postgres (GIN indexes from pharma 0002), difflib
on SQLite (tests, local dev).
"""

from difflib import get_close_matches

from django.contrib.postgres.search import TrigramSimilarity
from django.db import connection
from django.db.models import Count, Q

from apps.companies.models import Company
from apps.core.text import normalize_name
from apps.countries.models import Country
from apps.pharma.models import Generic, GenericSynonym, Product

from .misses import record_miss

LIMIT = 8
MIN_QUERY = 2


# Words people add to a drug name that the catalogue stores elsewhere (form, strength, salt).
NOISE = frozenset(
    "hydrochloride hcl sodium injection injectable tablet tablets bolus oral suspension powder "
    "solution drench pour on paste gel mg ml kg gm gram iv im sc vet veterinary for".split()
)


def core_query(q: str) -> str:
    """The query without salt/form/strength words and bare numbers: 'albendazole 10% oral' ->
    'albendazole'. Falls back to the original if nothing is left."""
    kept = [t for t in q.split() if t not in NOISE and not t.isdigit()]
    return " ".join(kept) or q


def _name_q(field: str, q: str, core: str) -> Q:
    """Contains the whole query, the core query, or every word of it (any order)."""
    cond = Q(**{f"{field}__contains": q}) | Q(**{f"{field}__contains": core})
    words = [w for w in core.split() if len(w) >= 3]
    if len(words) > 1:
        all_words = Q()
        for w in words:
            all_words &= Q(**{f"{field}__contains": w})
        cond |= all_words
    return cond


def _rank(name: str, q: str) -> int:
    n = normalize_name(name)
    return 0 if n == q else 1 if n.startswith(q) else 2


def _generics(q: str, core: str):
    direct = list(Generic.objects.listed().filter(_name_q("normalized_name", q, core)))
    via_syn = list(
        Generic.objects.listed().filter(
            pk__in=GenericSynonym.objects.filter(_name_q("normalized_synonym", q, core)).values(
                "generic"
            )
        )
    )
    via_ingredient = list(
        Generic.objects.listed().filter(_name_q("ingredients__normalized_name", q, core))
    )
    seen, out = set(), []
    for g in direct + via_syn + via_ingredient:
        if g.pk not in seen:
            seen.add(g.pk)
            out.append(g)
    return sorted(out, key=lambda g: (_rank(g.name, core), g.name))[:LIMIT]


TRIGRAM_CUTOFF = 0.3


def _trigram_generics(q: str):
    """Postgres: rank generics and synonyms by trigram similarity (uses the GIN indexes)."""
    by_name = (
        Generic.objects.listed()
        .annotate(sim=TrigramSimilarity("normalized_name", q))
        .filter(sim__gte=TRIGRAM_CUTOFF)
    )
    by_syn = (
        GenericSynonym.objects.filter(generic__in=Generic.objects.listed())
        .annotate(sim=TrigramSimilarity("normalized_synonym", q))
        .filter(sim__gte=TRIGRAM_CUTOFF)
        .select_related("generic")
    )
    scored = {g.pk: (g.sim, g) for g in by_name}
    for s in by_syn:
        if s.generic_id not in scored or scored[s.generic_id][0] < s.sim:
            scored[s.generic_id] = (s.sim, s.generic)
    ranked = sorted(scored.values(), key=lambda t: (-t[0], t[1].name))
    return [g for _, g in ranked[:LIMIT]]


def _fuzzy_generics(q: str):
    if connection.vendor == "postgresql":
        return _trigram_generics(q)
    names = {g.normalized_name: g for g in Generic.objects.listed()}
    for syn in GenericSynonym.objects.filter(generic__in=Generic.objects.listed()).select_related(
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


def _fuzzy_brands_and_companies(q: str) -> list[str]:
    """Brand and company names close to a mistyped query (trigram on Postgres, else difflib)."""
    products, companies = Product.objects.listed(), Company.objects.listed()
    if connection.vendor == "postgresql":
        brands = (
            products.annotate(sim=TrigramSimilarity("normalized_brand_name", q))
            .filter(sim__gte=TRIGRAM_CUTOFF)
            .order_by("-sim", "brand_name")[:LIMIT]
        )
        firms = (
            companies.annotate(sim=TrigramSimilarity("normalized_name", q))
            .filter(sim__gte=TRIGRAM_CUTOFF)
            .order_by("-sim", "name")[:LIMIT]
        )
        return [p.brand_name for p in brands] + [c.name for c in firms]
    names = {p.normalized_brand_name: p.brand_name for p in products}
    names.update({c.normalized_name: c.name for c in companies})
    return [names[n] for n in get_close_matches(q, names.keys(), n=LIMIT, cutoff=0.75)]


def _fallback() -> dict:
    """What to show when nothing matches: the best-covered generics and the active countries."""
    popular = (
        Generic.objects.listed()
        .annotate(n=Count("products", filter=Q(products__in=Product.objects.listed())))
        .filter(n__gt=0)
        .order_by("-n", "name")[:6]
    )
    return {
        "popular_generics": [{"name": g.name, "slug": g.slug} for g in popular],
        "countries": [
            {"name": c.name, "iso2": c.iso2} for c in Country.objects.filter(is_active=True)[:12]
        ],
    }


def search(query: str) -> dict:
    q = normalize_name(query)
    empty = {
        "query": query,
        "generics": [],
        "products": [],
        "companies": [],
        "did_you_mean": [],
        "fallback": None,
    }
    if len(q) < MIN_QUERY:
        return empty
    core = core_query(q)
    generics = _generics(q, core)
    brand_match = Product.objects.listed().filter(_name_q("normalized_brand_name", q, core))
    products = list(
        brand_match.select_related("generic", "manufacturer").order_by("brand_name")[:LIMIT]
    )
    if len(products) < LIMIT and generics:  # brands that contain a matched generic
        have = {p.pk for p in products}
        extra = (
            Product.objects.listed()
            .filter(generic__in=[g.pk for g in generics])
            .exclude(pk__in=have)
            .select_related("generic", "manufacturer")
            .order_by("brand_name")[: LIMIT - len(products)]
        )
        products += list(extra)
    companies = list(
        Company.objects.listed()
        .filter(_name_q("normalized_name", q, core))
        .order_by("name")[:LIMIT]
    )
    did_you_mean, fallback = [], None
    if not (generics or products or companies):
        for probe in dict.fromkeys([core, q]):
            did_you_mean += [g.name for g in _fuzzy_generics(probe) if g.name not in did_you_mean]
            did_you_mean += [n for n in _fuzzy_brands_and_companies(probe) if n not in did_you_mean]
        did_you_mean = did_you_mean[:LIMIT]
        fallback = _fallback()
        record_miss(query, q)  # nothing matched: tells staff which data to import
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
        "fallback": fallback,
    }
