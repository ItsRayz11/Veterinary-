"""Deterministic interaction lookup between reviewed generics. No model involved."""

from apps.clinical.models import Interaction, Severity
from apps.pharma.models import Generic
from apps.pharma.serializers import source_payload
from apps.sources.models import sources_for

MAX_GENERICS = 8
ORDER = {
    s: i
    for i, s in enumerate(
        [Severity.CONTRAINDICATED, Severity.MAJOR, Severity.MODERATE, Severity.MINOR]
    )
}


def check(slugs: list[str]) -> dict:
    slugs = list(dict.fromkeys(s.strip() for s in slugs if s.strip()))[:MAX_GENERICS]
    found = {g.slug: g for g in Generic.objects.public().filter(slug__in=slugs)}
    ids = [g.pk for g in found.values()]
    rows = (
        Interaction.objects.public()
        .filter(generic_a__in=ids, generic_b__in=ids)
        .select_related("generic_a", "generic_b")
    )
    interactions = sorted(
        (
            {
                "a": {"name": r.generic_a.name, "slug": r.generic_a.slug},
                "b": {"name": r.generic_b.name, "slug": r.generic_b.slug},
                "severity": r.severity,
                "description": r.description,
                "sources": source_payload([(s, "") for s in sources_for(r)]),
                "development_data": r.is_development_data,
            }
            for r in rows
        ),
        key=lambda i: (ORDER.get(i["severity"], 9), i["a"]["name"], i["b"]["name"]),
    )
    return {
        "checked": [{"name": g.name, "slug": g.slug} for g in found.values()],
        "unresolved": [s for s in slugs if s not in found],
        "interactions": interactions,
        "note": (
            "Only reviewed interactions are listed. No result does not mean a combination is "
            "safe: check the product labels and a current reference."
        ),
    }
