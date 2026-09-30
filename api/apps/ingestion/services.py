"""Product import pipeline: parse -> stage -> match -> staff approval -> unreviewed catalogue rows.

Approving a row never makes anything public: created records start as `needs_verification`, keep a
link to the import's Source, and only become public through the normal review workflow.
"""

import csv
import hashlib
import io

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.companies.models import Company, CompanyAlias
from apps.core.models import AuditLog, ReviewStatus
from apps.core.text import normalize_name
from apps.pharma.models import Generic, GenericSynonym, Product, ProductRegistration
from apps.pharma.models import RegistrationStatus as RegStatus
from apps.sources.models import Source, SourceLink

from .models import ImportBatch, RowStatus, StagedRecord

MAX_BYTES = 2_000_000
MAX_ROWS = 5000
REQUIRED = ("brand_name", "generic_name", "manufacturer")
OPTIONAL = ("registration_number", "registration_status")
HEADER_ALIASES = {
    "brand": "brand_name",
    "product": "brand_name",
    "product_name": "brand_name",
    "generic": "generic_name",
    "composition": "generic_name",
    "company": "manufacturer",
    "manufacturer_name": "manufacturer",
    "reg_no": "registration_number",
    "registration_no": "registration_number",
    "reg_status": "registration_status",
}


def _header(name: str) -> str:
    key = name.strip().lower().replace(" ", "_")
    return HEADER_ALIASES.get(key, key)


def parse_csv(text: str) -> list[dict]:
    """Rows as dicts with canonical headers. Raises ValidationError for unusable files."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValidationError(f"File is larger than {MAX_BYTES // 1_000_000} MB.")
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames:
        raise ValidationError("The file is empty.")
    mapping = {f: _header(f) for f in reader.fieldnames}
    missing = [c for c in REQUIRED if c not in mapping.values()]
    if missing:
        raise ValidationError(f"Missing required column(s): {', '.join(missing)}.")
    rows = []
    for raw in reader:
        rows.append({mapping[k]: (v or "").strip() for k, v in raw.items() if k in mapping})
        if len(rows) > MAX_ROWS:
            raise ValidationError(f"More than {MAX_ROWS} rows; split the file.")
    if not rows:
        raise ValidationError("The file has a header but no rows.")
    return rows


def find_generic(name: str) -> Generic | None:
    key = normalize_name(name)
    if not key:
        return None
    hit = Generic.objects.filter(normalized_name=key).first()
    if hit:
        return hit
    syn = GenericSynonym.objects.filter(normalized_synonym=key).select_related("generic").first()
    return syn.generic if syn else None


def find_company(name: str, country) -> Company | None:
    key = normalize_name(name)
    if not key:
        return None
    hit = Company.objects.filter(country=country, normalized_name=key).first()
    if hit:
        return hit
    alias = CompanyAlias.objects.filter(normalized_alias=key).select_related("company").first()
    return alias.company if alias else None


class Matcher:
    """In-memory lookups so staging a whole file costs a fixed number of queries.

    Loads names once (generics, synonyms, the country's companies and aliases, their existing
    brands and the country's registration numbers) instead of querying per row.
    """

    def __init__(self, country):
        self.country = country
        self._generics = dict(Generic.objects.values_list("normalized_name", "pk"))
        for key, generic_id in GenericSynonym.objects.values_list(
            "normalized_synonym", "generic_id"
        ):
            self._generics.setdefault(key, generic_id)
        self._companies = dict(
            Company.objects.filter(country=country).values_list("normalized_name", "pk")
        )
        for key, company_id in CompanyAlias.objects.values_list("normalized_alias", "company_id"):
            self._companies.setdefault(key, company_id)
        self._products = {
            (m, b): pk
            for m, b, pk in Product.objects.filter(
                manufacturer__in=set(self._companies.values())
            ).values_list("manufacturer_id", "normalized_brand_name", "pk")
        }
        self._numbers = set(
            ProductRegistration.objects.filter(country=country).values_list(
                "registration_number", flat=True
            )
        )

    def generic_id(self, name: str):
        return self._generics.get(normalize_name(name))

    def company_id(self, name: str):
        return self._companies.get(normalize_name(name))

    def product_id(self, company_id, brand: str):
        return self._products.get((company_id, normalize_name(brand)))

    def has_number(self, number: str) -> bool:
        return number in self._numbers


def _match(row: StagedRecord, country, matcher: Matcher | None = None) -> None:
    """Fill match fields and flag duplicates/errors on a staged row.

    Pass a `Matcher` when processing many rows (no queries per row); without one each lookup
    queries the database, which is fine for a single interactive approval.
    """
    if not (row.brand_name and row.generic_name and row.manufacturer_name):
        row.status, row.message = RowStatus.ERROR, "Brand, generic and manufacturer are required."
        return
    if row.registration_status and row.registration_status not in RegStatus.values:
        row.status = RowStatus.ERROR
        row.message = f"Unknown registration status '{row.registration_status}'."
        return
    if matcher is not None:
        row.matched_generic_id = matcher.generic_id(row.generic_name)
        row.matched_company_id = matcher.company_id(row.manufacturer_name)
        if row.matched_company_id:
            row.matched_product_id = matcher.product_id(row.matched_company_id, row.brand_name)
        number_taken = bool(row.registration_number) and matcher.has_number(row.registration_number)
    else:
        row.matched_generic = find_generic(row.generic_name)
        row.matched_company = find_company(row.manufacturer_name, country)
        if row.matched_company:
            row.matched_product = Product.objects.filter(
                manufacturer=row.matched_company,
                normalized_brand_name=normalize_name(row.brand_name),
            ).first()
        number_taken = (
            bool(row.registration_number)
            and ProductRegistration.objects.filter(
                country=country, registration_number=row.registration_number
            ).exists()
        )
    if row.matched_product_id:
        row.status, row.message = RowStatus.DUPLICATE, "This brand already exists for the company."
    elif number_taken:
        row.status = RowStatus.DUPLICATE
        row.message = "This registration number already exists in this country."


@transaction.atomic
def stage_batch(
    *, user, country, source_data: dict, csv_text: str, file_name: str = ""
) -> ImportBatch:
    rows = parse_csv(csv_text)
    checksum = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    if ImportBatch.objects.filter(kind="products", country=country, checksum=checksum).exists():
        raise ValidationError("This exact file was already imported for this country.")
    source = Source(
        source_type=source_data.get("source_type") or "other",
        title=source_data.get("title", "").strip(),
        publisher=source_data.get("publisher", "").strip(),
        url=source_data.get("url", "").strip(),
        license_note=source_data.get("license_note", "").strip(),
        country=country,
        accessed_date=timezone.localdate(),
        checksum=checksum,
    )
    if not source.title:
        raise ValidationError("A source title is required.")
    if not (source.url or source.publisher):
        raise ValidationError("Give the source URL or publisher so the data can be traced.")
    if not source.license_note:
        raise ValidationError("Record the source's licence/terms note before importing.")
    try:
        source.full_clean()
    except ValidationError as exc:
        raise ValidationError(exc.messages) from exc
    source.save()
    batch = ImportBatch.objects.create(
        country=country,
        source=source,
        file_name=file_name[:200],
        checksum=checksum,
        created_by=user,
    )
    staged = []
    matcher = Matcher(country)
    for i, raw in enumerate(rows, start=1):
        row = StagedRecord(
            batch=batch,
            row_number=i,
            raw=raw,
            brand_name=raw.get("brand_name", "")[:200],
            generic_name=raw.get("generic_name", "")[:200],
            manufacturer_name=raw.get("manufacturer", "")[:200],
            registration_number=raw.get("registration_number", "")[:100],
            registration_status=raw.get("registration_status", "").lower()[:16],
        )
        _match(row, country, matcher)
        staged.append(row)
    StagedRecord.objects.bulk_create(staged)
    AuditLog.objects.create(
        actor=user,
        action="import_staged",
        object_type=batch._meta.label,
        object_id=str(batch.pk),
        after={"rows": len(staged), "checksum": checksum},
        reason=source.title,
    )
    return batch


def _link(source: Source, obj) -> None:
    SourceLink.objects.get_or_create(
        source=source,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        locator="",
    )


@transaction.atomic
def approve_row(row: StagedRecord, by, *, check_complete: bool = True) -> StagedRecord:
    """Create (or reuse) generic, company, product and registration as UNREVIEWED records."""
    if row.status not in (RowStatus.PENDING, RowStatus.DUPLICATE):
        raise ValidationError("Only pending rows can be approved.")
    batch = row.batch
    row.status, row.message = RowStatus.PENDING, ""  # re-evaluate against current catalogue
    _match(row, batch.country)
    if row.status in (RowStatus.ERROR, RowStatus.DUPLICATE):
        raise ValidationError(row.message or "This row cannot be approved.")
    source = batch.source
    generic = row.matched_generic
    if generic is None:
        generic = Generic.objects.create(
            name=row.generic_name, review_status=ReviewStatus.NEEDS_VERIFICATION
        )
        _link(source, generic)
    company = row.matched_company
    if company is None:
        company = Company.objects.create(
            name=row.manufacturer_name,
            country=batch.country,
            is_manufacturer=True,
            review_status=ReviewStatus.NEEDS_VERIFICATION,
        )
        _link(source, company)
    try:
        with transaction.atomic():
            product = Product.objects.create(
                brand_name=row.brand_name,
                generic=generic,
                manufacturer=company,
                review_status=ReviewStatus.NEEDS_VERIFICATION,
            )
    except IntegrityError as exc:
        raise ValidationError("This brand already exists for the company.") from exc
    _link(source, product)
    if row.registration_number:
        reg = ProductRegistration.objects.create(
            product=product,
            country=batch.country,
            registration_number=row.registration_number,
            status=row.registration_status or RegStatus.UNKNOWN,
            review_status=ReviewStatus.NEEDS_VERIFICATION,
        )
        _link(source, reg)
    row.matched_generic, row.matched_company, row.matched_product = generic, company, product
    row.status, row.message = RowStatus.APPROVED, ""
    row.resolved_by, row.resolved_at = by, timezone.now()
    row.save()
    AuditLog.objects.create(
        actor=by,
        action="import_row_approved",
        object_type=row._meta.label,
        object_id=str(row.pk),
        after={"product": product.pk, "batch": batch.pk},
    )
    if check_complete:
        _maybe_complete(batch)
    return row


@transaction.atomic
def reject_row(row: StagedRecord, by, reason: str) -> StagedRecord:
    if row.status not in (RowStatus.PENDING, RowStatus.DUPLICATE, RowStatus.ERROR):
        raise ValidationError("This row was already resolved.")
    if not reason.strip():
        raise ValidationError("A reason is required to reject a row.")
    row.status, row.message = RowStatus.REJECTED, reason.strip()[:300]
    row.resolved_by, row.resolved_at = by, timezone.now()
    row.save()
    AuditLog.objects.create(
        actor=by,
        action="import_row_rejected",
        object_type=row._meta.label,
        object_id=str(row.pk),
        reason=reason[:300],
    )
    _maybe_complete(row.batch)
    return row


APPROVE_CHUNK = 50


def approve_clean(batch: ImportBatch, by, limit: int = APPROVE_CHUNK) -> dict:
    """Approve up to `limit` clean pending rows (each approval writes ~20 rows, and a request
    must finish inside the platform time limit). Call again while `remaining` is above zero.

    Returns counts: approved, skipped (flagged when re-checked) and remaining pending rows.
    """
    done = skipped = 0
    rows = batch.rows.filter(status=RowStatus.PENDING).select_related("batch__country")
    for row in rows[:limit]:
        try:
            approve_row(row, by, check_complete=False)
            done += 1
        except ValidationError as exc:
            skipped += 1
            # Persist why it was skipped (the failed approval rolled back its own writes), so the
            # row leaves the pending list and repeated calls make progress.
            if row.status == RowStatus.PENDING:
                row.status, row.message = RowStatus.DUPLICATE, " ".join(exc.messages)[:300]
            row.save(update_fields=["status", "message", "updated_at"])
    _maybe_complete(batch)
    return {
        "approved": done,
        "skipped": skipped,
        "remaining": batch.rows.filter(status=RowStatus.PENDING).count(),
    }


def _maybe_complete(batch: ImportBatch) -> None:
    if not batch.rows.filter(status__in=(RowStatus.PENDING,)).exists():
        batch.status = "completed"
        batch.save(update_fields=["status", "updated_at"])
