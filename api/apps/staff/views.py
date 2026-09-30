from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole, IsEditor, IsModerator
from apps.automation import tasks as automation_tasks
from apps.automation.models import Feed, JobRun, SourceHealth
from apps.core.models import AuditLog
from apps.core.schema import untyped_schema
from apps.education.models import QuestionReport
from apps.opportunities.models import Job, ListingStatus, Scholarship
from apps.pricing import services as price_services
from apps.pricing.models import PriceSubmission, SubmissionStatus

from . import services


class IsAdminRole(HasRole):
    roles = frozenset({Role.ADMIN})


@untyped_schema
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


@untyped_schema
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


@untyped_schema
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


@untyped_schema
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


@untyped_schema
@api_view(["GET"])
@permission_classes([IsModerator])
def price_submissions(request):
    qs = (
        PriceSubmission.objects.filter(status=request.query_params.get("status", "pending"))
        .select_related("pack", "country", "submitted_by", "target")
        .order_by("-created_at")[:100]
    )
    return Response({"results": [_serialize_submission(s) for s in qs]})


@untyped_schema
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


@untyped_schema
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


@untyped_schema
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


@untyped_schema
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


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def automation_status(request):
    runs = JobRun.objects.all()[:20]
    broken = (
        SourceHealth.objects.filter(ok=False)
        .select_related("source")
        .order_by("-consecutive_failures", "-checked_at")[:50]
    )
    return Response(
        {
            "can_run": request.user.is_superuser or request.user.role == Role.ADMIN,
            "tasks": sorted(automation_tasks.TASKS),
            "runs": [
                {
                    "id": r.pk,
                    "task": r.task,
                    "status": r.status,
                    "summary": r.summary,
                    "error": r.error,
                    "at": r.created_at,
                }
                for r in runs
            ],
            "broken_sources": [
                {
                    "id": h.source_id,
                    "title": h.source.title,
                    "url": h.source.url,
                    "error": h.error,
                    "failures": h.consecutive_failures,
                    "checked_at": h.checked_at,
                }
                for h in broken
            ],
            "feeds": [
                {
                    "id": f.pk,
                    "name": f.name,
                    "kind": f.kind,
                    "enabled": f.enabled,
                    "last_run_at": f.last_run_at,
                    "last_result": f.last_result,
                }
                for f in Feed.objects.all()
            ],
        }
    )


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAdminRole])
def automation_run(request, task):
    if task not in automation_tasks.TASKS:
        return Response({"detail": "Unknown task."}, status=http.HTTP_404_NOT_FOUND)
    run = automation_tasks.run_task(task)
    AuditLog.objects.create(
        actor=request.user,
        action="automation_run_manually",
        object_type=run._meta.label,
        object_id=str(run.pk),
        after={"task": task, "status": run.status},
    )
    return Response(
        {"task": run.task, "status": run.status, "summary": run.summary, "error": run.error}
    )
