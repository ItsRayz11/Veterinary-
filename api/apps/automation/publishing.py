"""Publishing factual regulator data as *official listings* (docs/PUBLICATION_TIERS.md).

An imported record starts as `imported_unverified` (hidden). It becomes an official listing
(`official_regulatory`) only when a source is fully approved (terms, field mapping, first batch)
and the record passes the factual checks below. Nothing here can create clinical sign-off:
only the factual catalogue models are touched, never doses, withdrawal periods, notes or
interactions, and `expert_reviewed` / `verified` are never set.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.companies.models import Company
from apps.core.models import AuditLog, ReviewStatus
from apps.pharma.models import Generic, Product, ProductRegistration
from apps.sources.models import SourceLink

from .models import DataSource

# The only models this module may ever promote. Clinical models are deliberately absent;
# test_publishing asserts that none of them is reachable from here.
FACTUAL_MODELS = (Generic, Company, Product, ProductRegistration)
VALID_STATUSES = {"registered", "expired", "suspended", "withdrawn", "unknown"}
MAX_SKIPPED_SHARE = 0.25  # a file where >25% of entries were unreadable has probably changed layout


@dataclass
class Validation:
    ok: list = field(default_factory=list)
    problems: Counter = field(default_factory=Counter)
    examples: dict = field(default_factory=dict)

    def reject(self, reg, why: str) -> None:
        self.problems[why] += 1
        self.examples.setdefault(why, f"{reg.registration_number} {reg.product.brand_name}")

    def as_dict(self) -> dict:
        return {
            "valid": len(self.ok),
            "rejected": sum(self.problems.values()),
            "problems": dict(self.problems),
            "examples": self.examples,
        }


def validate_registrations(source: DataSource) -> Validation:
    """Factual completeness of the source's still-hidden registrations."""
    result = Validation()
    regs = ProductRegistration.objects.filter(
        data_source=source, review_status=ReviewStatus.IMPORTED_UNVERIFIED
    ).select_related("product__generic", "product__manufacturer")
    linked = set(
        SourceLink.objects.filter(content_type__model="productregistration").values_list(
            "object_id", flat=True
        )
    )
    for reg in regs.iterator(chunk_size=1000):
        p = reg.product
        if not reg.registration_number.strip():
            result.reject(reg, "missing registration number")
        elif reg.status not in VALID_STATUSES:
            result.reject(reg, "unrecognised status")
        elif not (p.brand_name.strip() and p.generic.name.strip() and p.manufacturer.name.strip()):
            result.reject(reg, "missing brand, generic or company")
        elif reg.pk not in linked:
            result.reject(reg, "no source link")
        elif p.is_development_data or reg.is_development_data:
            result.reject(reg, "development data")
        else:
            result.ok.append(reg)
    return result


@transaction.atomic
def promote(source: DataSource, registrations, by, *, reason: str) -> dict:
    """Move validated registrations, and the factual records they depend on, to official listing."""
    ids = [r.pk for r in registrations]
    hidden = ReviewStatus.IMPORTED_UNVERIFIED
    products = Product.objects.filter(registrations__in=ids, review_status=hidden).distinct()
    generics = Generic.objects.filter(products__in=products, review_status=hidden).distinct()
    companies = Company.objects.filter(
        Q(manufactured_products__in=products) | Q(marketed_products__in=products),
        review_status=hidden,
    ).distinct()
    now = timezone.now()
    counts, audit = {}, []
    for qs in (generics, companies, products, ProductRegistration.objects.filter(pk__in=ids)):
        model = qs.model
        if model not in FACTUAL_MODELS:  # structural guard, see module docstring
            raise RuntimeError(f"{model.__name__} can never be published as an official listing")
        pks = list(qs.values_list("pk", flat=True))
        model.objects.filter(pk__in=pks, review_status=hidden).update(
            review_status=ReviewStatus.OFFICIAL_REGULATORY,
            reviewed_by=by,
            reviewed_at=now,
            updated_at=now,
        )
        counts[model.__name__.lower()] = len(pks)
        audit += [
            AuditLog(
                actor=by,
                action="published_official_listing",
                object_type=model._meta.label,
                object_id=str(pk),
                before={"review_status": hidden},
                after={"review_status": ReviewStatus.OFFICIAL_REGULATORY},
                reason=reason[:500],
            )
            for pk in pks
        ]
    AuditLog.objects.bulk_create(audit, batch_size=1000)
    return counts


def approve_mapping(source: DataSource, user) -> None:
    source.mapping_approved_at, source.mapping_approved_by = timezone.now(), user
    source.save(update_fields=["mapping_approved_at", "mapping_approved_by", "updated_at"])
    _audit(user, "source_mapping_approved", source)


def approve_first_batch(source: DataSource, user) -> dict:
    """The one human gate. Publishes the valid records of the staged first batch; afterwards
    routine factual updates publish automatically if the source's `auto_publish` switch is on."""
    if not source.terms_confirmed_at:
        raise ValueError("Confirm the publisher's terms first.")
    if not source.mapping_approved_at:
        raise ValueError("Approve the field mapping first.")
    if not (source.regulator_name and source.attribution_text):
        raise ValueError("Set the regulator name and the licence attribution text first.")
    validation = validate_registrations(source)
    if not validation.ok:
        raise ValueError("There are no valid staged records to publish.")
    counts = promote(source, validation.ok, user, reason=f"First batch approved for {source.slug}")
    source.first_batch_approved_at, source.first_batch_approved_by = timezone.now(), user
    source.held_reason = ""
    source.save(
        update_fields=[
            "first_batch_approved_at",
            "first_batch_approved_by",
            "held_reason",
            "updated_at",
        ]
    )
    _audit(user, "source_first_batch_approved", source, after={**counts, **validation.as_dict()})
    return {"published": counts, "validation": validation.as_dict()}


def release_hold(source: DataSource, user) -> None:
    """Accept a held change: the next sync skips the safety guard once."""
    source.held_reason, source.guard_bypass_once = "", True
    source.update_available = True
    source.save(
        update_fields=["held_reason", "guard_bypass_once", "update_available", "updated_at"]
    )
    _audit(user, "source_hold_released", source)


def sync_guard(source: DataSource, cleaned) -> str:
    """Why this sync must wait for a person, or '' if it looks like a routine update."""
    if source.guard_bypass_once:
        return ""
    prior, new = source.record_count, len(cleaned.rows)
    if prior:
        if new < prior * (1 - source.max_removal_pct / 100):
            return f"file shrank from {prior} to {new} records (limit {source.max_removal_pct}%)"
        if new > prior * (1 + source.max_growth_pct / 100):
            return f"file grew from {prior} to {new} records (limit {source.max_growth_pct}%)"
    seen = cleaned.report.get("entries") or cleaned.report.get("veterinary_products") or 0
    skipped = cleaned.report.get("skipped_incomplete", 0)
    if seen and skipped / seen > MAX_SKIPPED_SHARE:
        return f"{skipped} of {seen} entries unreadable; the file layout may have changed"
    return ""


def publish_after_sync(source: DataSource, by) -> dict:
    """Called at the end of a successful sync. Publishes only for fully approved sources."""
    validation = validate_registrations(source)
    if not source.may_auto_publish:
        return {
            "published": {},
            "held_back": len(validation.ok),
            "validation": validation.as_dict(),
        }
    counts = promote(source, validation.ok, by, reason=f"Routine update from {source.slug}")
    return {"published": counts, "validation": validation.as_dict()}


def _audit(user, action: str, source: DataSource, after=None) -> None:
    AuditLog.objects.create(
        actor=user,
        action=action,
        object_type=source._meta.label,
        object_id=str(source.pk),
        after=after,
        reason=source.slug,
    )
