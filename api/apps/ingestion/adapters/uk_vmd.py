"""UK Veterinary Medicines Directorate Product Information Database snapshot (XML).

Source: https://www.vmd.defra.gov.uk/ProductInformationDatabase/ (Open Government Licence v3.0).
Current authorised products become registrations "registered", suspended ones "suspended";
expired and homeopathic entries are skipped. The file carries no strengths or withdrawal periods
(those are only in the linked SPC documents), so none are created: the SPC link is kept in the
notes for the reviewer. Everything is staged as unreviewed.
"""

import io
from collections import Counter

from defusedxml import ElementTree

from .common import NAME_MAX, Cleaned, join_generic, squash

SECTIONS = {"CurrentAuthorisedProducts": "registered", "SuspendedProducts": "suspended"}


def split_substances(text: str) -> list[str]:
    """Split on commas outside brackets: 'Milbemycin Oxime (A3 and A4), Praziquantel'."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return [squash(p) for p in parts if squash(p)]


def _notes(fields: dict[str, str]) -> str:
    labels = [
        ("TargetSpecies", "Target species"),
        ("PharmaceuticalForm", "Form"),
        ("TherapeuticGroup", "Therapeutic group"),
        ("DistributionCategory", "Distribution category"),
        ("AuthorisationRoute", "Authorisation route"),
        ("Territory", "Territory"),
        ("SPC_Link", "Summary of product characteristics"),
    ]
    return "; ".join(f"{label}: {fields[key]}" for key, label in labels if fields.get(key))[:900]


def clean_snapshot(xml: bytes) -> Cleaned:
    rows: list[dict] = []
    report: Counter = Counter()
    seen: set[str] = set()
    for _event, el in ElementTree.iterparse(io.BytesIO(xml)):
        tag = el.tag
        if tag not in SECTIONS and tag not in ("ExpiredProducts", "HomeopathicProducts"):
            continue
        report["entries"] += 1
        if tag not in SECTIONS:
            report["skipped_" + tag] += 1
            el.clear()
            continue
        fields = {c.tag: squash(c.text or "") for c in el}
        el.clear()
        name, holder = fields.get("Name", ""), fields.get("MAHolder", "")
        number = fields.get("VMNo", "")
        substances = split_substances(fields.get("ActiveSubstances", ""))
        if not (name and holder and substances):
            report["skipped_incomplete"] += 1
            continue
        if len(name) > NAME_MAX:
            report["skipped_name_too_long"] += 1
            continue
        if number and number in seen:
            report["skipped_duplicate_number"] += 1
            continue
        seen.add(number)
        rows.append(
            {
                "brand_name": name,
                "generic_name": join_generic(substances),
                "manufacturer": holder,
                "registration_number": number,
                "registration_status": SECTIONS[tag],
                "composition": ", ".join(substances),
                "notes": _notes(fields),
            }
        )
        report["rows"] += 1
    return Cleaned(rows, dict(report))
