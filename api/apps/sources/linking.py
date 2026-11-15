"""Turns raw URLs on imported records into linked, deduplicated, validated Source entities.

Root cause this fixes: importers stored a plain `source_url` on the record but never created the
`Source`/`SourceLink` rows that the review workflow (and `set_review_status`) look at, so a record
with a perfectly good Wikipedia URL still showed "No source linked". A URL string is evidence; a
Source is the registry entity that carries identity, licence and verification state.

Everything here is deterministic and idempotent. The record's own URL fields are never changed or
removed (original provenance is preserved); a Source is only ever added, filled in where it was
blank, or merged with an exact duplicate.
"""

import re
from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.core.licensing import is_open_license

from .models import Source, SourceLink, VerificationStatus
from .providers import provider_for_url
from .urlutil import canonicalize_url, host_of

QID = re.compile(r"^Q\d{1,12}$")


@dataclass
class LinkResult:
    linked: int = 0  # SourceLinks that exist after the call for this record
    created_links: int = 0
    created_sources: int = 0
    problems: list[str] = field(default_factory=list)


def source_candidates(record) -> list[dict]:
    """Every piece of source evidence the record carries, as kwargs for `resolve_source`."""
    out: list[dict] = []
    url = (getattr(record, "source_url", "") or "").strip()
    if url:
        p = provider_for_url(url)
        out.append(
            {
                "url": url,
                "title": f"{p.name if p else 'Source'}: {record}"[:500],
                "publisher": p.publisher if p else "",
                "license_note": getattr(record, "source_license", "")
                or (p.license_note if p else ""),
                "license_url": p.license_url if p else "",
                "source_type": p.source_type if p else "other",
            }
        )
    qid = (getattr(record, "wikidata_id", "") or "").strip()
    if QID.match(qid):
        p = provider_for_url("https://www.wikidata.org/")
        out.append(
            {
                "url": f"https://www.wikidata.org/wiki/{qid}",
                "title": f"Wikidata: {record} ({qid})"[:500],
                "publisher": p.publisher,
                "license_note": p.license_note,
                "license_url": p.license_url,
                "source_type": p.source_type,
            }
        )
    return out


def resolve_source(
    *, url, title, publisher="", license_note="", license_url="", source_type="other"
) -> tuple[Source | None, bool]:
    """The registry Source for this URL: matched by canonical URL, else created. (None, False)
    when the URL is not a usable http(s) address. Blank fields on a match are filled, never
    overwritten."""
    canon = canonicalize_url(url)
    if not canon:
        return None, False
    existing = Source.objects.filter(canonical_url=canon).order_by("pk").first()
    if existing:
        fill = {
            k: v
            for k, v in {
                "publisher": publisher,
                "license_note": license_note,
                "license_url": license_url,
            }.items()
            if v and not getattr(existing, k)
        }
        if fill:
            for k, v in fill.items():
                setattr(existing, k, v)
            existing.save(update_fields=[*fill, "updated_at"])
        return existing, False
    p = provider_for_url(url)
    source = Source.objects.create(
        source_type=source_type,
        title=title[:500],
        publisher=publisher[:300],
        url=url[:1000],
        license_note=license_note[:300],
        license_url=license_url[:500],
        provider=p.slug if p else "",
        accessed_date=timezone.localdate(),
    )
    return source, True


def validate_source(source: Source, *, save: bool = True) -> tuple[str, str]:
    """Metadata checks only (URL shape, publisher identity from the host, licence). Whether the
    page is reachable is the link checker's job. Returns (status, note)."""
    status = VerificationStatus.UNVERIFIED
    note = "Publisher not recognised; needs a person to vouch."
    canon = canonicalize_url(source.url)
    provider = provider_for_url(source.url)
    if source.url and not canon:
        status, note = VerificationStatus.INVALID, "The URL is not a valid http(s) address."
    elif not source.url:
        note = "No URL; only a DOI or publisher is recorded."
    elif source.provider and provider and source.provider != provider.slug:
        status = VerificationStatus.CONFLICT
        note = f"Registered as '{source.provider}' but the address belongs to {provider.name}."
    elif provider:
        lic = source.license_note or provider.license_note
        if source.license_note and not is_open_license(source.license_note):
            # The publisher publishes an open licence but the entry claims something else.
            status = VerificationStatus.CONFLICT if provider.open_license else status
            note = (
                f"Licence '{source.license_note}' differs from {provider.name}'s published "
                f"licence '{provider.license_note}'."
            )
        elif not is_open_license(lic):
            note = f"Publisher recognised ({provider.name}) but its licence is not an open one."
        else:
            status = VerificationStatus.PROVENANCE_OK
            note = f"Address belongs to {provider.name}; licence {lic}."
    else:
        ds = _registered_data_source(source.url)
        if ds is not None and ds.terms_confirmed_at and ds.licence_note:
            status = VerificationStatus.PROVENANCE_OK
            note = (
                f"Registered data source '{ds.slug}', terms confirmed; licence {ds.licence_note}."
            )
    if save:
        changed = {
            "verification_status": status.value,
            "verification_note": note[:300],
            "provider": source.provider or (provider.slug if provider else ""),
        }
        if provider and not source.license_note:
            changed["license_note"] = provider.license_note
            changed["license_url"] = source.license_url or provider.license_url
        if status == VerificationStatus.PROVENANCE_OK and source.verification_status != status:
            changed["verified_at"] = timezone.now()
        for k, v in changed.items():
            setattr(source, k, v)
        source.save(update_fields=[*changed, "updated_at"])
    return status, note


def _registered_data_source(url: str):
    from apps.automation.models import DataSource  # avoid an import cycle at module load

    host = host_of(url)
    if not host:
        return None
    for ds in DataSource.objects.all():
        if host in {host_of(ds.landing_url), host_of(ds.data_url)}:
            return ds
    return None


@transaction.atomic
def link_record(record) -> LinkResult:
    """Ensure each source URL the record carries is a linked, validated Source. Idempotent."""
    result = LinkResult()
    ct = ContentType.objects.get_for_model(record)
    for cand in source_candidates(record):
        source, created = resolve_source(**cand)
        if source is None:
            result.problems.append(f"unusable source URL: {cand['url'][:80]}")
            continue
        result.created_sources += created
        validate_source(source)
        _, made = SourceLink.objects.get_or_create(
            source=source, content_type=ct, object_id=record.pk, locator=""
        )
        result.created_links += made
    result.linked = SourceLink.objects.filter(content_type=ct, object_id=record.pk).count()
    return result


def _license_key(value: str) -> str:
    return re.sub(r"\W+", " ", (value or "").lower()).strip()


def _repoint_other_references(dup: Source, keep: Source) -> None:
    """Move every remaining foreign key that points at `dup` (questions, prices, import runs)."""
    for rel in Source._meta.related_objects:
        if rel.related_model is SourceLink or not (rel.one_to_many or rel.many_to_one):
            continue
        rel.related_model.objects.filter(**{rel.field.name: dup}).update(**{rel.field.name: keep})


@transaction.atomic
def _merge_group(sources: list[Source]) -> tuple[int, int]:
    """Merge exact duplicates (same canonical URL) into the oldest. Entries whose stated licences
    disagree are not merged; both are flagged as conflicting for a person to resolve."""
    from apps.automation.models import SourceHealth
    from apps.core.models import AuditLog

    keep, merged, conflicts = sources[0], 0, 0
    for dup in sources[1:]:
        a, b = _license_key(keep.license_note), _license_key(dup.license_note)
        if a and b and a != b:
            for s in (keep, dup):
                s.verification_status = VerificationStatus.CONFLICT
                s.verification_note = "Duplicate registry entries state different licences."
                s.save(update_fields=["verification_status", "verification_note", "updated_at"])
            conflicts += 1
            continue
        for k in ("publisher", "author", "doi", "license_note", "license_url", "edition"):
            if not getattr(keep, k) and getattr(dup, k):
                setattr(keep, k, getattr(dup, k))
        keep.save()
        for link in list(dup.links.all()):
            if SourceLink.objects.filter(
                source=keep,
                content_type_id=link.content_type_id,
                object_id=link.object_id,
                locator=link.locator,
            ).exists():
                link.delete()
            else:
                link.source = keep
                link.save(update_fields=["source"])
        health = SourceHealth.objects.filter(source=dup).first()
        if health:
            if SourceHealth.objects.filter(source=keep).exists():
                health.delete()
            else:
                health.source = keep
                health.save(update_fields=["source", "updated_at"])
        _repoint_other_references(dup, keep)
        AuditLog.objects.create(
            action="source_merged",
            object_type=Source._meta.label,
            object_id=str(keep.pk),
            before={"merged_source_id": dup.pk, "url": dup.url, "title": dup.title},
            after={"kept_source_id": keep.pk},
            reason="Exact duplicate by canonical URL",
        )
        dup.delete()
        merged += 1
    return merged, conflicts


def dedupe_sources() -> dict:
    """Collapse registry entries that point at the same page. Safe to run repeatedly."""
    dupes = (
        Source.objects.exclude(canonical_url="")
        .values("canonical_url")
        .annotate(n=Count("pk"))
        .filter(n__gt=1)
        .values_list("canonical_url", flat=True)
    )
    merged = conflicts = 0
    for canon in list(dupes):
        m, c = _merge_group(list(Source.objects.filter(canonical_url=canon).order_by("pk")))
        merged, conflicts = merged + m, conflicts + c
    return {"merged": merged, "conflicts": conflicts}
