from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole, IsEditor, IsModerator
from apps.core.models import AuditLog
from apps.education.models import QuestionReport
from apps.opportunities.models import Job, ListingStatus, Scholarship
from apps.pricing import services as price_services
from apps.pricing.models import PriceSubmission, SubmissionStatus

from . import services


class IsAdminRole(HasRole):
    roles = frozenset({Role.ADMIN})


@api_view(["GET"])
@permission_classes([IsEditor])
def summary(request):
    return Response(
        {
            "review_queue": services.queue_counts(),
            "price_submissions_pending": PriceSubmission.objects.filter(
                status=SubmissionStatus.PENDING
            ).count(),
            "question_reports_open": QuestionReport.objects.filter(resolved=False).count(),
            "listings_pending": Job.objects.filter(status=ListingStatus.PENDING).count()
            + Scholarship.objects.filter(status=ListingStatus.PENDING).count(),
            "role": request.user.role,
            "can_approve_clinical": request.user.can_approve_clinical,
        }
    )


@api_view(["GET"])
@permission_classes([IsEditor])
def review_queue(request):
    model_key = request.query_params.get("model", "")
    models = services.publishable_models()
    if model_key and model_key not in models:
        return Response({"detail": "Unknown model."}, status=http.HTTP_400_BAD_REQUEST)
    default = ",".join(s.value for s in services.QUEUE_STATUSES)
    statuses = (request.query_params.get("status") or default).split(",")
    items = []
    for key, m in models.items():
        if model_key and key != model_key:
            continue
        for obj in m.objects.filter(review_status__in=statuses).order_by("-updated_at")[:50]:
            items.append(services.serialize_record(key, obj))
    items.sort(key=lambda i: i["updated_at"], reverse=True)
    return Response({"results": items[:100]})


@api_view(["POST"])
@permission_classes([IsEditor])
def set_status(request, model_key, pk):
    obj, error, code = services.change_status(
        model_key,
        pk,
        str(request.data.get("status", "")),
        request.user,
        str(request.data.get("reason", ""))[:300],
    )
    if error:
        return Response({"detail": error}, status=code)
    return Response(services.serialize_record(model_key, obj))


@api_view(["GET"])
@permission_classes([IsEditor])
def record_history(request, model_key, pk):
    obj = services.get_record(model_key, pk)
    if obj is None or not hasattr(obj, "history"):
        return Response({"detail": "No history for this record."}, status=http.HTTP_404_NOT_FOUND)
    return Response({"label": str(obj), "versions": services.history_diff(obj)})


def _serialize_submission(s: PriceSubmission) -> dict:
    return {
        "id": s.pk,
        "kind": s.kind,
        "status": s.status,
        "product": str(s.pack),
        "country": s.country.name,
        "region": s.region,
        "city": s.city,
        "currency": s.currency or s.country.currency_code,
        "price_type": s.price_type,
        "amount": str(s.amount) if s.amount is not None else None,
        "target": str(s.target) if s.target_id else None,
        "note": s.note,
        "evidence_url": s.evidence_url,
        "submitted_by": s.submitted_by.username,
        "created_at": s.created_at,
    }


@api_view(["GET"])
@permission_classes([IsModerator])
def price_submissions(request):
    qs = (
        PriceSubmission.objects.filter(status=request.query_params.get("status", "pending"))
        .select_related("pack", "country", "submitted_by", "target")
        .order_by("-created_at")[:100]
    )
    return Response({"results": [_serialize_submission(s) for s in qs]})


@api_view(["POST"])
@permission_classes([IsModerator])
def moderate_submission(request, pk, decision):
    if decision not in ("approve", "reject"):
        return Response({"detail": "Unknown decision."}, status=http.HTTP_400_BAD_REQUEST)
    sub = (
        PriceSubmission.objects.filter(pk=pk)
        .select_related("pack", "country", "submitted_by", "target")
        .first()
    )
    if sub is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    note = str(request.data.get("note", ""))
    try:
        if decision == "approve":
            price_services.approve_submission(sub, request.user, note)
        else:
            price_services.reject_submission(sub, request.user, note)
    except PermissionDenied as exc:
        return Response({"detail": str(exc)}, status=http.HTTP_403_FORBIDDEN)
    except ValidationError as exc:
        return Response({"detail": " ".join(exc.messages)}, status=http.HTTP_400_BAD_REQUEST)
    sub.refresh_from_db()
    return Response(_serialize_submission(sub))


@api_view(["GET"])
@permission_classes([IsModerator])
def question_reports(request):
    qs = QuestionReport.objects.filter(resolved=False).select_related("question", "reporter")[:100]
    return Response(
        {
            "results": [
                {
                    "id": r.pk,
                    "question_id": r.question_id,
                    "question": r.question.stem[:200],
                    "message": r.message,
                    "reporter": r.reporter.username,
                    "created_at": r.created_at,
                }
                for r in qs
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsModerator])
def resolve_question_report(request, pk):
    r = QuestionReport.objects.filter(pk=pk, resolved=False).first()
    if r is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    r.resolved = True
    r.save(update_fields=["resolved", "updated_at"])
    AuditLog.objects.create(
        actor=request.user,
        action="question_report_resolved",
        object_type=r._meta.label,
        object_id=str(r.pk),
        before={"resolved": False},
        after={"resolved": True},
        reason=str(request.data.get("note", ""))[:300],
    )
    return Response({"id": r.pk, "resolved": True})


@api_view(["GET"])
@permission_classes([IsAdminRole])
def audit_log(request):
    rows = AuditLog.objects.select_related("actor").order_by("-id")[:100]
    return Response(
        {
            "results": [
                {
                    "id": a.pk,
                    "at": a.at,
                    "actor": getattr(a.actor, "username", None),
                    "action": a.action,
                    "object": f"{a.object_type} #{a.object_id}",
                    "reason": a.reason,
                }
                for a in rows
            ]
        }
    )
