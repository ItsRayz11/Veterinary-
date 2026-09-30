from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsModerator
from apps.core.schema import untyped_schema
from apps.core.throttling import UserThrottle
from apps.countries.models import Country

from . import services
from .models import Job, Listing, ListingStatus, Scholarship


class SubmitThrottle(UserThrottle):
    scope = "submit"


def _kind(kind: str):
    model = services.KINDS.get(kind)
    if model is None:
        raise DRFValidationError({"kind": "Unknown listing type."})
    return model


def _msg(exc: ValidationError) -> str:
    return " ".join(exc.messages)


def _public(item: Listing, kind: str) -> dict:
    data = {
        "id": item.pk,
        "kind": kind,
        "title": item.title,
        "organization": item.organization,
        "country": item.country.iso2 if item.country_id else None,
        "country_name": item.country.name if item.country_id else None,
        "description": item.description,
        "apply_url": item.apply_url,
        "closes_on": item.closes_on,
        "expires_on": item.expires_on,
    }
    if isinstance(item, Job):
        data.update({"city": item.city, "job_type": item.job_type})
    else:
        data.update({"level": item.level, "funding": item.funding})
    return data


class ListingSerializer(serializers.ModelSerializer):
    country = serializers.SlugRelatedField(
        slug_field="iso2",
        queryset=Country.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    def validate_apply_url(self, value):
        if not value.lower().startswith(("http://", "https://")):
            raise serializers.ValidationError("Use a web link starting with http:// or https://.")
        return value

    def validate_closes_on(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("The closing date is in the past.")
        return value


class JobSerializer(ListingSerializer):
    class Meta:
        model = Job
        fields = (
            "title",
            "organization",
            "country",
            "city",
            "job_type",
            "description",
            "apply_url",
            "closes_on",
        )


class ScholarshipSerializer(ListingSerializer):
    class Meta:
        model = Scholarship
        fields = (
            "title",
            "organization",
            "country",
            "level",
            "funding",
            "description",
            "apply_url",
            "closes_on",
        )


SERIALIZERS = {"jobs": JobSerializer, "scholarships": ScholarshipSerializer}


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def listings(request, kind):
    model = _kind(kind)
    qs = model.objects.public().select_related("country")
    p = request.query_params
    if p.get("country"):
        qs = qs.filter(country__iso2=p["country"].upper())
    if p.get("type") and kind == "jobs":
        qs = qs.filter(job_type=p["type"])
    if p.get("level") and kind == "scholarships":
        qs = qs.filter(level=p["level"])
    if p.get("q"):
        q = p["q"][:100]
        qs = qs.filter(
            Q(title__icontains=q) | Q(organization__icontains=q) | Q(description__icontains=q)
        )
    qs = qs.order_by("expires_on", "-created_at")[:100]
    return Response([_public(i, kind) for i in qs])


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def listing_detail(request, kind, pk):
    item = get_object_or_404(_kind(kind).objects.public().select_related("country"), pk=pk)
    return Response(_public(item, kind))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SubmitThrottle])
def submit(request, kind):
    model = _kind(kind)
    try:
        services.check_can_submit(request.user, model)
    except ValidationError as exc:
        raise DRFValidationError({"detail": _msg(exc)}) from exc
    s = SERIALIZERS[kind](data=request.data)
    s.is_valid(raise_exception=True)
    item = s.save(submitted_by=request.user)
    return Response({"id": item.pk, "status": item.status}, status=status.HTTP_201_CREATED)


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SubmitThrottle])
def report(request, kind, pk):
    item = get_object_or_404(_kind(kind).objects.public(), pk=pk)
    try:
        services.report(item, request.user, str(request.data.get("message", "")))
    except ValidationError as exc:
        raise DRFValidationError({"message": _msg(exc)}) from exc
    return Response(status=status.HTTP_201_CREATED)


# ---- staff moderation ----


def _staff_row(item: Listing, kind: str) -> dict:
    return {
        **_public(item, kind),
        "status": item.status,
        "submitted_by": item.submitted_by.username,
        "moderation_note": item.moderation_note,
        "created_at": item.created_at,
    }


@untyped_schema
@api_view(["GET"])
@permission_classes([IsModerator])
def staff_listings(request):
    wanted = request.query_params.get("status", ListingStatus.PENDING)
    rows = []
    for kind, model in services.KINDS.items():
        qs = model.objects.filter(status=wanted).select_related("country", "submitted_by")[:100]
        rows.extend(_staff_row(i, kind) for i in qs)
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return Response({"results": rows})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsModerator])
def staff_decide(request, kind, pk, decision):
    item = get_object_or_404(_kind(kind).objects.select_related("country", "submitted_by"), pk=pk)
    note = str(request.data.get("note", ""))
    try:
        if decision == "approve":
            services.approve(item, request.user, note)
        elif decision == "reject":
            services.reject(item, request.user, note)
        else:
            return Response({"detail": "Unknown decision."}, status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except ValidationError as exc:
        return Response({"detail": _msg(exc)}, status=status.HTTP_400_BAD_REQUEST)
    item.refresh_from_db()
    return Response(_staff_row(item, kind))
