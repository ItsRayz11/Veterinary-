"""Deterministic first-pass triage of user reports and submissions.

Pure rules, no AI call: cheap, explainable and safe to run on every item. Anything touching
clinical advice is flagged for a qualified human; nothing is auto-resolved or auto-published.
"""

import re
from dataclasses import dataclass, field

SPAM = re.compile(
    r"(https?://\S+.*){3,}|\b(viagra|casino|crypto|loan|whatsapp me|click here)\b", re.I
)
CLINICAL = re.compile(
    r"\b(dose|dosage|mg/kg|overdose|toxic|poison|inject|withdrawal period|contraindicat|"
    r"treat(ment)?|diagnos|antibiotic|euthan)\w*",
    re.I,
)
ABUSE = re.compile(r"\b(idiot|stupid|scam|fraud)\b", re.I)


@dataclass
class Triage:
    category: str  # spam | clinical | duplicate | needs_citation | ok
    escalate_to_clinician: bool = False
    reasons: list[str] = field(default_factory=list)


def triage_report(message: str, *, has_citation: bool, duplicates_open: int = 0) -> Triage:
    text = message or ""
    if SPAM.search(text):
        return Triage("spam", reasons=["looks like spam (links or promotional terms)"])
    if duplicates_open:
        return Triage("duplicate", reasons=[f"{duplicates_open} other open report(s) on this item"])
    if CLINICAL.search(text):
        return Triage(
            "clinical",
            escalate_to_clinician=True,
            reasons=["mentions dosing, treatment or diagnosis: veterinarian reviewer needed"],
        )
    if not has_citation and len(text) > 40 and not ABUSE.search(text):
        return Triage("needs_citation", reasons=["claims a correction without a source"])
    return Triage("ok")
