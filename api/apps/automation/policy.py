"""Deterministic publication policy shared by every automated pipeline.

The rule is deliberately conservative and does not depend on AI confidence: records that carry
clinical, dosage, regulatory or safety claims are never auto-published; everything else needs
independently verified rules (a licensed source, a verified link, no conflicts) to skip review.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Provenance(StrEnum):
    COLLECTED = "collected"
    UNVERIFIED = "unverified"
    AI_ASSISTED = "ai_assisted"
    VERIFIED_FROM_SOURCE = "verified_from_source"
    HUMAN_REVIEWED = "human_reviewed"
    PUBLISHED = "published"
    STALE = "stale"
    REJECTED = "rejected"


class Decision(StrEnum):
    PUBLISH = "publish"
    REVIEW = "review"
    SKIP = "skip"


# Content kinds that always need a qualified human, whatever the confidence.
HIGH_STAKES_KINDS = frozenset(
    {"dose", "treatment", "diagnosis", "regulatory", "safety", "withdrawal", "interaction",
     "drug_reference", "policy_advice", "clinical_answer"}
)  # fmt: skip
LOW_RISK_KINDS = frozenset({"job", "scholarship", "listing", "university", "link_update"})


@dataclass
class Candidate:
    kind: str
    source_verified: bool = False  # source is registered, enabled, terms confirmed
    destination_ok: bool = False  # URL/deadline independently verified (e.g. link resolves)
    ai_assisted: bool = False
    is_duplicate: bool = False
    conflicts_with_existing: bool = False
    expired: bool = False
    suspicious: bool = False  # payment demand, scam markers, price outlier ...
    ai_confidence: float | None = None  # recorded for display only, never used to publish
    reasons: list[str] = field(default_factory=list)


def decide(c: Candidate) -> tuple[Decision, list[str]]:
    reasons: list[str] = []
    if c.expired:
        return Decision.SKIP, ["expired"]
    if c.is_duplicate:
        return Decision.SKIP, ["duplicate of an existing record"]
    if c.kind in HIGH_STAKES_KINDS or c.kind not in LOW_RISK_KINDS:
        reasons.append("high-stakes or unknown kind: qualified reviewer required")
    if c.suspicious:
        reasons.append("flagged as suspicious")
    if c.conflicts_with_existing:
        reasons.append("conflicts with an existing record")
    if c.ai_assisted:
        reasons.append("AI-assisted content is never published unreviewed")
    if not c.source_verified:
        reasons.append("source is not verified")
    if not c.destination_ok:
        reasons.append("destination/deadline not independently verified")
    return (Decision.REVIEW, reasons) if reasons else (Decision.PUBLISH, ["low-risk, verified"])


PRICE_OUTLIER_FACTOR = 5


def is_price_outlier(amount: float, reference: list[float]) -> bool:
    """True when a price is wildly off from trusted references (median based). Pure arithmetic."""
    if len(reference) < 3 or amount <= 0:
        return False
    ref = sorted(reference)
    median = ref[len(ref) // 2]
    return amount > median * PRICE_OUTLIER_FACTOR or amount < median / PRICE_OUTLIER_FACTOR


SCAM_MARKERS = (
    "registration fee", "processing fee", "pay to apply", "application fee", "western union",
    "moneygram", "send money", "advance fee", "pay a fee", "deposit required",
)  # fmt: skip


def looks_suspicious(text: str) -> bool:
    """Payment-demand and similar scam markers in a posting (plain substring checks)."""
    t = (text or "").lower()
    return any(m in t for m in SCAM_MARKERS)
