"""Find the reviewed records a question is about and render them as numbered context blocks.

Only `public()` (reviewed) generics, doses and notes are ever used. Nothing here calls a model.
"""

from dataclasses import dataclass

from apps.clinical.models import ClinicalNote, DoseRegimen
from apps.core.models import ReviewStatus
from apps.core.text import normalize_name
from apps.pharma.models import Generic, GenericSynonym, Product

MAX_GENERICS = 3
MAX_DOSES = 12
MAX_NOTES = 12


@dataclass
class Context:
    tag: str  # G1, G2...
    generic: Generic
    text: str


def _fmt(value) -> str:
    return f"{value.normalize():f}" if value is not None else ""


MAX_NGRAM = 6  # longest name (in words) that can be recognised
MAX_TOKENS = 60  # only the start of a long question is searched


def _candidates(question_norm: str) -> list[str]:
    """Every run of 1..MAX_NGRAM consecutive words in the question."""
    tokens = question_norm.split()[:MAX_TOKENS]
    return sorted(
        {
            " ".join(tokens[i:j])
            for i in range(len(tokens))
            for j in range(i + 1, min(len(tokens), i + MAX_NGRAM) + 1)
        }
    )


def find_generics(question: str) -> list[Generic]:
    """Reviewed generics named in the question, via generic name, synonym or brand name.

    Whole-word matching done as indexed IN lookups on the word runs of the question, so the cost
    depends on the question's length, not on how many drugs and brands the catalogue holds.
    """
    names = _candidates(normalize_name(question))
    if not names:
        return []
    public = Generic.objects.public()
    hits: dict[int, Generic] = {g.pk: g for g in public.filter(normalized_name__in=names)}
    for syn in GenericSynonym.objects.filter(
        normalized_synonym__in=names, generic__in=public
    ).select_related("generic"):
        hits.setdefault(syn.generic_id, syn.generic)
    for product in (
        Product.objects.public()
        .filter(normalized_brand_name__in=names, generic__in=public)
        .select_related("generic")
    ):
        hits.setdefault(product.generic_id, product.generic)
    return sorted(hits.values(), key=lambda g: g.name)[:MAX_GENERICS]


def _label(obj) -> str:
    code = ReviewStatus(obj.review_status).label
    return f"status={code}{' (development data)' if obj.is_development_data else ''}"


def build_context(generics: list[Generic]) -> list[Context]:
    out = []
    for i, g in enumerate(generics, start=1):
        tag = f"G{i}"
        lines = [f"[{tag}] {g.name}" + (f" (class: {g.drug_class.name})" if g.drug_class else "")]
        if g.description:
            lines.append(f"Description: {g.description}")
        if g.mechanism:
            lines.append(f"Mechanism: {g.mechanism}")
        doses = (
            DoseRegimen.objects.public()
            .filter(generic=g, product__isnull=True)
            .select_related("species", "indication", "route", "dose_unit", "max_single_dose_unit")
            .order_by("species__sort_order", "id")[:MAX_DOSES]
        )
        for d in doses:
            parts = [
                f"species={d.species.name}",
                f"indication={d.indication.name}" if d.indication_id else "",
                f"route={d.route.code}",
                f"dose={_fmt(d.dose_min)} to {_fmt(d.dose_max)} {d.dose_unit.code}",
                f"interval_hours={_fmt(d.interval_hours)}" if d.interval_hours else "",
                f"duration_days={_fmt(d.duration_min_days)} to {_fmt(d.duration_max_days)}"
                if d.duration_min_days
                else "",
                f"max_single_dose={_fmt(d.max_single_dose)} {d.max_single_dose_unit.code}"
                if d.max_single_dose
                else "",
                f"note={d.notes}" if d.notes else "",
                _label(d),
            ]
            lines.append("Dose: " + "; ".join(p for p in parts if p))
        for n in (
            ClinicalNote.objects.public().filter(generic=g).select_related("species")[:MAX_NOTES]
        ):
            sp = f", species={n.species.name}" if n.species_id else ""
            lines.append(f"Note ({n.kind}{sp}, {_label(n)}): {n.text}")
        out.append(Context(tag=tag, generic=g, text="\n".join(lines)))
    return out
