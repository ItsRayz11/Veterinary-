"""Deterministic assessment of a record: grouping facets, completeness, issues, duplicates,
change detection and a publication recommendation.

No AI and no network. The recommendation is advice for a person; publication itself still goes
through `apps.core.review.set_review_status` (source required, sign-off roles enforced) or,
for regulator imports, the DataSource publication tiers. `safe_batch` only ever means "a
reviewer may approve this in a bulk action"; it never publishes anything on its own.
"""

import hashlib
import json
from datetime import timedelta
from difflib import SequenceMatcher

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.core.licensing import is_open_license
from apps.core.models import PUBLIC_STATUSES, ReviewStatus
from apps.core.text import normalize_name
from apps.sources.models import SourceLink, VerificationStatus
from apps.sources.providers import provider_for_url
from apps.sources.urlutil import canonicalize_url

from . import policy
from .models import ImageAsset, ImageStatus, RecordAssessment, SourceHealth

SAFE_COMPLETENESS = 80
REASSESS_AFTER = timedelta(hours=24)
FUZZY_NAME = 0.92

# model_key -> policy kind. Anything not listed is treated as high-stakes by policy.decide().
MODEL_KIND = {"universities.university": "university"}
# Factual regulator catalogue models: published through DataSource tiers, never by bulk approval.
REGULATOR_MODELS = frozenset(
    {"pharma.generic", "pharma.product", "pharma.productregistration", "companies.company"}
)
REQUIRED_FIELDS = {
    "universities.university": [
        "name", "country", "city", "website", "summary", "source_url", "source_license",
    ],
}  # fmt: skip
_TECHNICAL = {
    "id",
    "created_at",
    "updated_at",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "slug",
}

ISSUES = {
    "no_source": "No source recorded",
    "raw_url_only": "Source URL is not linked to the registry",
    "source_unverified": "Source not yet verified",
    "source_conflict": "Conflicting source or licence evidence",
    "source_invalid": "Source is invalid",
    "link_failing": "Source link is failing",
    "license_missing": "Licence missing",
    "license_conflict": "Licence on the record conflicts with the source",
    "incomplete": "Missing information",
    "duplicate_candidate": "Possible duplicate",
    "image_failed": "Image could not be stored",
    "image_rejected": "Image licence does not allow copying",
    "image_pending": "Image waiting to be stored",
    "changed_since_import": "Changed since previous import",
    "suspicious": "Flagged as suspicious",
    "development_data": "Development/seed data",
    "high_risk": "Safety-critical content",
}
# The issue a record is grouped under when it has several (most blocking first).
ISSUE_ORDER = [
    "development_data", "suspicious", "source_invalid", "source_conflict", "license_conflict",
    "no_source", "raw_url_only", "duplicate_candidate", "license_missing", "incomplete",
    "source_unverified", "link_failing", "image_failed", "image_rejected", "image_pending",
    "changed_since_import", "high_risk",
]  # fmt: skip
RECOMMENDATIONS = {
    "safe_batch": "Eligible for safe batch approval",
    "review": "Needs human review",
    "clinical_review": "Needs authorized clinical review",
    "regulator_review": "Governed by regulator data-source approval",
    "fix_source": "Source needs repair",
    "duplicate": "Resolve possible duplicate",
    "incomplete": "Complete the missing information",
    "blocked": "Blocked",
}


def content_fields(record) -> dict[str, str]:
    """Reviewable content of a record as plain strings (used for hashing and change diffs)."""
    out = {}
    for f in record._meta.concrete_fields:
        if (
            f.name in _TECHNICAL
            or f.name.startswith("normalized_")
            or f.name == "is_development_data"
        ):
            continue
        value = getattr(record, f.attname, None)
        out[f.name] = "" if value is None else str(value)
    return out


def _filled(value) -> bool:
    return value is not None and str(value).strip() != ""


def completeness(record, model_key: str) -> tuple[int, list[str]]:
    wanted = REQUIRED_FIELDS.get(model_key)
    if wanted is None:  # generic: descriptive text fields the schema allows to be blank
        wanted = [
            f.name
            for f in record._meta.concrete_fields
            if f.editable
            and f.blank
            and not f.is_relation
            and f.get_internal_type() in ("CharField", "TextField", "URLField")
            and f.name not in _TECHNICAL
            and not f.name.startswith(("normalized_", "image_"))
        ]
    if not wanted:
        return 100, []
    missing = []
    for name in wanted:
        field = record._meta.get_field(name)
        value = getattr(record, field.attname, None)
        if not _filled(value):
            missing.append(
                field.verbose_name.capitalize() if hasattr(field, "verbose_name") else name
            )
    return round(100 * (len(wanted) - len(missing)) / len(wanted)), missing


def find_duplicates(record, limit: int = 5) -> list[dict]:
    model = type(record)
    label = str(record)
    norm = normalize_name(label)
    base = model.objects.exclude(pk=record.pk)
    found: dict[int, dict] = {}

    def add(other, reason):
        found.setdefault(
            other.pk,
            {
                "model": model._meta.label_lower,
                "id": other.pk,
                "label": str(other),
                "reason": reason,
            },
        )

    qid = getattr(record, "wikidata_id", "")
    if qid:
        for o in base.filter(wikidata_id=qid)[:limit]:
            add(o, "same Wikidata item")
    site = canonicalize_url(getattr(record, "website", "") or "")
    if site:
        host_path = site
        for o in base.exclude(website="").filter(website__icontains=site.split("//", 1)[-1][:60])[
            :50
        ]:
            if canonicalize_url(o.website) == host_path:
                add(o, "same website")
    scope = base
    if "country_id" in {f.attname for f in model._meta.concrete_fields}:
        scope = base.filter(country_id=record.country_id)
    for o in scope.order_by("pk")[:1500]:
        ratio = SequenceMatcher(None, norm, normalize_name(str(o))).ratio()
        if ratio >= FUZZY_NAME:
            add(o, f"near-identical name ({round(ratio * 100)}%)")
    return list(found.values())[:limit]


def _source_picture(record) -> dict:
    ct = ContentType.objects.get_for_model(record)
    links = list(
        SourceLink.objects.filter(content_type=ct, object_id=record.pk).select_related("source")
    )
    sources = [lk.source for lk in links]
    health = {
        h.source_id: h for h in SourceHealth.objects.filter(source_id__in=[s.pk for s in sources])
    }
    raw = bool((getattr(record, "source_url", "") or "").strip())
    statuses = {s.verification_status for s in sources}
    if not sources:
        state = "raw_url_only" if raw else "none"
    elif VerificationStatus.INVALID in statuses:
        state = "invalid"
    elif VerificationStatus.CONFLICT in statuses:
        state = "conflict"
    elif VerificationStatus.PROVENANCE_OK in statuses:
        state = "linked_ok"
    else:
        state = "linked_unverified"
    failing = any(
        (h := health.get(s.pk)) and not h.ok and h.consecutive_failures >= 2 for s in sources
    )
    destination_ok = (
        state == "linked_ok"
        and not failing
        and any(
            (h := health.get(s.pk)) and h.ok
            for s in sources
            if s.verification_status == VerificationStatus.PROVENANCE_OK
        )
    )
    provider = next((s.provider for s in sources if s.provider), "")
    if not provider and getattr(record, "source_url", ""):
        p = provider_for_url(record.source_url)
        provider = p.slug if p else ""
    ds = getattr(record, "data_source", None)
    if not provider and ds is not None:
        provider = ds.slug
    return {
        "sources": sources,
        "state": state,
        "failing": failing,
        "destination_ok": destination_ok,
        "provider": provider or "unknown",
        "license_conflict": _license_conflict(record, sources),
    }


def _license_conflict(record, sources) -> bool:
    stated = (getattr(record, "source_license", "") or "").strip()
    if not stated or not sources:
        return False
    open_sources = [s for s in sources if s.license_note and is_open_license(s.license_note)]
    return bool(open_sources) and not is_open_license(stated)


def _image_state(record) -> tuple[str, list[ImageAsset]]:
    ct = ContentType.objects.get_for_model(record)
    assets = list(
        ImageAsset.objects.filter(content_type=ct, object_id=record.pk).exclude(
            status=ImageStatus.SUPERSEDED
        )
    )
    if not assets:
        return ("pending" if getattr(record, "image_url", "") else "none"), assets
    states = {a.status for a in assets}
    if ImageStatus.FAILED in states:
        return "failed", assets
    if ImageStatus.PENDING in states:
        return "pending", assets
    if ImageStatus.STORED in states:
        return "stored", assets
    return "rejected", assets


def assess(record, *, now=None) -> RecordAssessment:
    """Build (or refresh) the RecordAssessment for one record. Idempotent."""
    now = now or timezone.now()
    ct = ContentType.objects.get_for_model(record)
    model_key = record._meta.label_lower
    pic = _source_picture(record)
    image_state, _assets = _image_state(record)
    pct, missing = completeness(record, model_key)
    dupes = find_duplicates(record)
    fields = content_fields(record)
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()

    previous = RecordAssessment.objects.filter(content_type=ct, object_id=record.pk).first()
    changed, changed_at = [], None
    if previous:
        changed, changed_at = list(previous.changed_fields), previous.changed_at
        if previous.content_hash and previous.content_hash != digest:
            old = previous.snapshot or {}
            changed = sorted(k for k in fields if old.get(k) != fields[k])
            changed_at = now
        elif previous.review_status != record.review_status:
            changed, changed_at = [], None  # a person acted on the record since: change is seen

    text = " ".join(fields.get(k, "") for k in ("name", "title", "summary", "description"))
    suspicious = policy.looks_suspicious(text)
    kind = MODEL_KIND.get(model_key, "drug_reference")
    high_risk = kind not in policy.LOW_RISK_KINDS
    reviewed_at = getattr(record, "reviewed_at", None)
    changed_after_review = bool(changed) and (
        record.review_status in PUBLIC_STATUSES
        and (reviewed_at is None or changed_at > reviewed_at)
    )

    issues = []
    if record.is_development_data:
        issues.append("development_data")
    if suspicious:
        issues.append("suspicious")
    state_issue = {
        "none": "no_source", "raw_url_only": "raw_url_only", "invalid": "source_invalid",
        "conflict": "source_conflict", "linked_unverified": "source_unverified",
    }.get(pic["state"])  # fmt: skip
    if state_issue:
        issues.append(state_issue)
    if pic["failing"]:
        issues.append("link_failing")
    if pic["license_conflict"]:
        issues.append("license_conflict")
    if pic["sources"] and not any(s.license_note for s in pic["sources"]):
        issues.append("license_missing")
    if pct < SAFE_COMPLETENESS:
        issues.append("incomplete")
    if dupes:
        issues.append("duplicate_candidate")
    issues += {
        "failed": ["image_failed"],
        "rejected": ["image_rejected"],
        "pending": ["image_pending"],
    }.get(image_state, [])
    if changed_after_review or (
        changed and previous and record.review_status not in PUBLIC_STATUSES
    ):
        issues.append("changed_since_import")
    if high_risk:
        issues.append("high_risk")
    issues = sorted(set(issues), key=ISSUE_ORDER.index)

    decision, why = policy.decide(
        policy.Candidate(
            kind=kind,
            source_verified=pic["state"] == "linked_ok",
            destination_ok=pic["destination_ok"],
            suspicious=suspicious,
            is_duplicate=False,
            conflicts_with_existing=bool(dupes),
        )
    )
    if "development_data" in issues or "suspicious" in issues:
        rec = "blocked"
    elif high_risk:
        rec = "regulator_review" if model_key in REGULATOR_MODELS else "clinical_review"
    elif (
        pic["state"] in ("none", "raw_url_only", "invalid", "conflict")
        or "license_conflict" in issues
    ):
        rec = "fix_source"
    elif dupes:
        rec = "duplicate"
    elif pct < SAFE_COMPLETENESS:
        rec = "incomplete"
    elif (
        decision == policy.Decision.PUBLISH and image_state != "failed" and not changed_after_review
    ):
        rec = "safe_batch"
    else:
        rec = "review"
    reasons = list(why)
    if rec == "safe_batch":
        reasons = [
            "Source verified with an open licence and a working link",
            f"{pct}% of expected fields present",
            "No duplicates, conflicts or safety-critical content",
        ]

    country = (
        getattr(record, "country", None)
        if "country_id" in {f.attname for f in record._meta.concrete_fields}
        else None
    )
    search = " ".join(
        [
            str(record), model_key, str(record.pk), pic["provider"],
            country.name if country else "", country.iso2 if country else "",
            getattr(record, "wikidata_id", "") or "",
            getattr(record, "source_url", "") or "",
            *(f"{s.title} {s.url}" for s in pic["sources"]),
            record._meta.verbose_name,
        ]
    ).lower()  # fmt: skip

    values = {
        "model_key": model_key,
        "label": str(record)[:300],
        "review_status": record.review_status,
        "is_development_data": record.is_development_data,
        "country_iso2": country.iso2 if country else "",
        "country_name": country.name if country else "",
        "provider": pic["provider"],
        "batch": record.created_at.date().isoformat(),
        "record_created_at": record.created_at,
        "record_updated_at": record.updated_at,
        "source_state": pic["state"],
        "trust_level": "high"
        if pic["destination_ok"]
        else ("medium" if pic["state"] in ("linked_ok", "linked_unverified") else "low"),
        "risk": "high" if high_risk else "low",
        "completeness": pct,
        "missing_fields": missing,
        "issues": issues,
        "issue_text": "|" + "|".join(issues) + "|" if issues else "",
        "primary_issue": issues[0] if issues else "",
        "duplicates": dupes,
        "image_state": image_state,
        "recommendation": rec,
        "reasons": reasons,
        "snapshot": fields,
        "content_hash": digest,
        "changed_fields": changed,
        "changed_at": changed_at,
        "search_text": search[:4000],
        "assessed_at": now,
    }
    obj, _ = RecordAssessment.objects.update_or_create(
        content_type=ct, object_id=record.pk, defaults=values
    )
    return obj


def stale_records(model, statuses, limit: int):
    """Records of `model` in `statuses` never assessed, changed since, or assessed long ago."""
    ct = ContentType.objects.get_for_model(model)
    seen = {
        a.object_id: a
        for a in RecordAssessment.objects.filter(content_type=ct).only(
            "object_id", "record_updated_at", "assessed_at", "review_status"
        )
    }
    cutoff = timezone.now() - REASSESS_AFTER
    out = []
    for pk, updated, status in model.objects.filter(review_status__in=statuses).values_list(
        "pk", "updated_at", "review_status"
    ):
        a = seen.get(pk)
        if (
            a is None
            or a.record_updated_at != updated
            or a.assessed_at < cutoff
            or a.review_status != status
        ):
            out.append(pk)
            if len(out) >= limit:
                break
    return model.objects.filter(pk__in=out)


def all_statuses() -> list[str]:
    return [s.value for s in ReviewStatus]
