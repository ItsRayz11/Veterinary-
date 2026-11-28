"""Turn failed searches into synonym suggestions an editor accepts with one click.

Two sources of suggestions, both pointing only at generics already in the public catalogue:
- spelling: the search's own typo-tolerant matcher (trigram on Postgres, difflib elsewhere);
- AI (on request): the provider routed for "tagging" names the international nonproprietary name
  the term most likely refers to. The answer is used only if that exact name (or a synonym of it)
  is already listed, and it is always shown as an AI suggestion for a person to accept.

Nothing here publishes on its own: accepting creates a GenericSynonym (a search alias, not a
clinical statement) and writes an audit entry. Per CLINICAL_GOVERNANCE.md, AI never produces
clinical values; this prompt asks for a drug name only.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.core.models import AuditLog
from apps.core.text import normalize_name
from apps.pharma.models import Generic, GenericSynonym

from .models import SearchMiss
from .services import _fuzzy_generics, core_query

MAX_SUGGESTIONS = 3
AI_TASK = "tagging"
AI_SYSTEM = (
    "You map a veterinary medicine search term to the international nonproprietary name (INN) "
    "of the active ingredient it most likely refers to. The term may be a brand name, a "
    "misspelling, a regional or transliterated name, or an abbreviation. Reply with the INN in "
    "English on one line and nothing else. If you are not confident, reply UNKNOWN. Never give "
    "doses, indications or any other clinical information."
)


def _as_suggestion(g: Generic, via: str) -> dict:
    return {"slug": g.slug, "name": g.name, "via": via}


def spelling_suggestions(miss: SearchMiss) -> list[dict]:
    q = normalize_name(miss.query)
    seen, out = set(), []
    for probe in dict.fromkeys([core_query(q), q]):
        for g in _fuzzy_generics(probe):
            if g.pk not in seen:
                seen.add(g.pk)
                out.append(_as_suggestion(g, "spelling"))
    return out[:MAX_SUGGESTIONS]


def _listed_generic_named(name: str) -> Generic | None:
    n = normalize_name(name)
    if not n:
        return None
    listed = Generic.objects.listed()
    hit = listed.filter(normalized_name=n).first()
    if hit:
        return hit
    syn = (
        GenericSynonym.objects.filter(normalized_synonym=n, generic__in=listed)
        .select_related("generic")
        .first()
    )
    return syn.generic if syn else None


def ai_suggestion(miss: SearchMiss, actor=None) -> dict:
    """Ask the configured provider. Returns {"suggestions": [...], "answer": str, "note": str}.

    Raises ai.client.AIError (safe to show) when no provider is set up or the call fails.
    """
    from apps.ai.client import run_task

    raw = run_task(AI_TASK, miss.example or miss.query, system=AI_SYSTEM, actor=actor)
    answer = (raw or "").strip().splitlines()[0].strip(" .\"'`")[:100] if raw else ""
    if not answer or answer.upper() == "UNKNOWN":
        return {"suggestions": [], "answer": "", "note": "The AI did not recognise this term."}
    g = _listed_generic_named(answer)
    if g is None:
        return {
            "suggestions": [],
            "answer": answer,
            "note": f"The AI suggested {answer}, which is not in the catalogue yet.",
        }
    return {"suggestions": [_as_suggestion(g, "ai")], "answer": answer, "note": ""}


@transaction.atomic
def accept(miss: SearchMiss, generic_slug: str, user) -> GenericSynonym | None:
    """Add the visitor's spelling as a synonym of a listed generic and close the miss."""
    generic = Generic.objects.listed().filter(slug=generic_slug).first()
    if generic is None:
        raise ValidationError("That generic is not in the public catalogue.")
    text = (miss.example or miss.query).strip()[:200]
    n = normalize_name(text)
    existing = GenericSynonym.objects.filter(normalized_synonym=n).select_related("generic").first()
    if existing and existing.generic_id != generic.pk:
        raise ValidationError(f"“{text}” is already a synonym of {existing.generic.name}.")
    synonym = None
    if existing is None and n != generic.normalized_name:
        try:
            synonym = GenericSynonym.objects.create(generic=generic, synonym=text)
        except IntegrityError as exc:  # a concurrent accept of the same spelling
            raise ValidationError("This spelling was just added; reload the list.") from exc
        AuditLog.objects.create(
            actor=user,
            action="search_synonym_added",
            object_type=GenericSynonym._meta.label,
            object_id=str(synonym.pk),
            after={"synonym": text, "generic": generic.slug},
            reason=f"failed search #{miss.pk} ({miss.count} searches)",
        )
    miss.resolved = True
    miss.save(update_fields=["resolved", "last_seen"])
    return synonym
