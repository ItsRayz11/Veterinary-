from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import IsEditor
from apps.core.schema import untyped_schema
from apps.countries.models import Country

from . import services
from .models import ImportBatch, StagedRecord


def _msg(exc: ValidationError) -> str:
    return " ".join(exc.messages)


def _batch(b: ImportBatch) -> dict:
    counts = dict(b.rows.values_list("status").annotate(n=Count("pk")))
    return {
        "id": b.pk,
        "kind": b.kind,
        "country": b.country.iso2,
        "file_name": b.file_name,
        "source": b.source.title,
        "license_note": b.source.license_note,
        "status": b.status,
        "created_at": b.created_at,
        "counts": counts,
    }


def _row(r: StagedRecord) -> dict:
    return {
        "id": r.pk,
        "row_number": r.row_number,
        "brand_name": r.brand_name,
        "generic_name": r.generic_name,
        "manufacturer": r.manufacturer_name,
        "registration_number": r.registration_number,
        "status": r.status,
        "message": r.message,
        "generic_match": r.matched_generic.name if r.matched_generic_id else None,
        "company_match": r.matched_company.name if r.matched_company_id else None,
    }


@untyped_schema
@api_view(["GET", "POST"])
@permission_classes([IsEditor])
def batches(request):
    if request.method == "GET":
        qs = ImportBatch.objects.select_related("country", "source")[:50]
        return Response({"results": [_batch(b) for b in qs]})
    country = Country.objects.filter(iso2=str(request.data.get("country", "")).upper()).first()
    if country is None:
        return Response({"detail": "Choose a country."}, status=http.HTTP_400_BAD_REQUEST)
    try:
        batch = services.stage_batch(
            user=request.user,
            country=country,
            source_data=request.data.get("source") or {},
            csv_text=str(request.data.get("csv_text", "")),
            file_name=str(request.data.get("file_name", "")),
        )
    except ValidationError as exc:
        return Response({"detail": _msg(exc)}, status=http.HTTP_400_BAD_REQUEST)
    return Response(_batch(batch), status=http.HTTP_201_CREATED)


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def batch_detail(request, pk):
    batch = get_object_or_404(ImportBatch.objects.select_related("country", "source"), pk=pk)
    rows = batch.rows.select_related("matched_generic", "matched_company")
    wanted = request.query_params.get("status")
    if wanted:
        rows = rows.filter(status=wanted)
    return Response({**_batch(batch), "rows": [_row(r) for r in rows[:200]]})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def resolve_row(request, pk, row_pk, decision):
    row = get_object_or_404(
        StagedRecord.objects.select_related("batch__country", "batch__source"),
        pk=row_pk,
        batch_id=pk,
    )
    try:
        if decision == "approve":
            services.approve_row(row, request.user)
        elif decision == "reject":
            services.reject_row(row, request.user, str(request.data.get("reason", "")))
        else:
            return Response({"detail": "Unknown decision."}, status=http.HTTP_400_BAD_REQUEST)
    except ValidationError as exc:
        return Response({"detail": _msg(exc)}, status=http.HTTP_400_BAD_REQUEST)
    row.refresh_from_db()
    return Response(_row(row))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def approve_all_clean(request, pk):
    batch = get_object_or_404(ImportBatch.objects.select_related("country", "source"), pk=pk)
    return Response(services.approve_clean(batch, request.user))
