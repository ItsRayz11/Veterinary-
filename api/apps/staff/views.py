from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole, IsEditor, IsModerator
from apps.automation import assessment, bulk, images, pipeline
from apps.automation import tasks as automation_tasks
from apps.automation.models import DataSource, Feed, ImageAsset, JobRun, SourceHealth
from apps.core.models import AuditLog
from apps.core.schema import untyped_schema
from apps.education.models import QuestionReport
from apps.opportunities.models import Job, ListingStatus, Scholarship
from apps.pricing import services as price_services
from apps.pricing.models import PriceSubmission, SubmissionStatus

from . import services, triage


class IsAdminRole(HasRole):
    roles = frozenset({Role.ADMIN})


def _extras(user) -> dict:
    """Counts for the dashboard from the newer modules (all plain database counts)."""
    from datetime import timedelta

    from django.db.models import Sum
    from django.utils import timezone

    from apps.ai.models import AIUsage
    from apps.content.models import Article, ArticleStatus
    from apps.marketplace.models import ApprovalStatus, Catalog3D, Lead, RetailerOffer, Supplier
    from apps.pricing.models import PriceRecord

    now = timezone.now()
    out = {
        "articles_in_review": Article.objects.filter(status=ArticleStatus.REVIEW).count(),
        "articles_published": Article.objects.public().count(),
        "prices_recent_7d": PriceRecord.objects.published()
        .filter(created_at__gte=now - timedelta(days=7))
        .count(),
    }
    if user.role in (Role.MODERATOR, Role.ADMIN) or user.is_superuser:
        out |= {
            "catalogs_pending": Catalog3D.objects.filter(status=ApprovalStatus.PENDING).count(),
            "suppliers_pending": Supplier.objects.filter(status=ApprovalStatus.PENDING).count(),
            "offers_pending": RetailerOffer.objects.filter(status=ApprovalStatus.PENDING).count(),
            "leads_new": Lead.objects.filter(status="new").count(),
        }
    if user.role == Role.ADMIN or user.is_superuser:
        month = AIUsage.objects.filter(at__gte=now.replace(day=1, hour=0, minute=0, second=0))
        out |= {
            "ai_month_calls": month.count(),
            "ai_month_cost_usd": str(month.aggregate(t=Sum("cost_usd"))["t"] or 0),
        }
    return out


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def summary(request):
    return Response(
        _extras(request.user)
        | {
            "review_queue": services.queue_counts(),
            "price_submissions_pending": PriceSubmission.objects.filter(
                status=SubmissionStatus.PENDING
            ).count(),
            "question_reports_open": QuestionReport.objects.filter(resolved=False).count(),
            "listings_pending": Job.objects.filter(status=ListingStatus.PENDING).count()
            + Scholarship.objects.filter(status=ListingStatus.PENDING).count(),
            "role": request.user.role,
            "admin_url": f"/{settings.ADMIN_URL}",
            "can_approve_clinical": request.user.can_approve_clinical,
        }
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def review_queue(request):
    model_key = request.query_params.get("model", "")
    if model_key and model_key not in services.publishable_models():
        return Response({"detail": "Unknown model."}, status=http.HTTP_400_BAD_REQUEST)
    default = ",".join(s.value for s in services.QUEUE_STATUSES)
    statuses = (request.query_params.get("status") or default).split(",")
    try:
        page = int(request.query_params.get("page", "1"))
    except ValueError:
        page = 1
    q = request.query_params.get("q", "").strip()[:100]
    return Response(services.queue_page(model_key, statuses, q, min(page, 1000)))


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def record_detail(request, model_key, pk):
    data = services.record_detail(model_key, pk)
    if data is None:
        return Response({"detail": "Record not found."}, status=http.HTTP_404_NOT_FOUND)
    return Response(data)


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
    assessment.assess(obj)
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
            "data_sources": [
                {
                    "id": d.pk,
                    "name": d.name,
                    "publisher": d.publisher,
                    "country": d.country_iso2,
                    "url": d.landing_url,
                    "licence": d.licence_note,
                    "monitored": d.enabled,
                    "reachable": d.last_ok,
                    "error": d.last_error,
                    "update_available": d.update_available,
                    "last_checked_at": d.last_checked_at,
                    "can_import": bool(d.importer),
                    "import_enabled": d.import_enabled,
                    "terms_confirmed": d.terms_confirmed_at is not None,
                    "last_imported_at": d.last_imported_at,
                    "last_import_result": d.last_import_result,
                }
                for d in DataSource.objects.all()
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


# ---------- source registry (admin only) ----------

SOURCE_FIELDS = (
    "slug name publisher country_iso2 kind landing_url data_url licence_note notes importer "
    "enabled import_enabled check_interval_hours content_type geography method robots_status "
    "extraction_scope credentials_ref import_destination priority rate_limit_per_hour paused"
).split()
SOURCE_FIELDS += (
    "regulator_name attribution_text licence_url auto_publish max_removal_pct max_growth_pct"
).split()
SOURCE_BOOLS = {"enabled", "import_enabled", "paused", "auto_publish"}
SOURCE_INTS = {
    "check_interval_hours",
    "priority",
    "rate_limit_per_hour",
    "max_removal_pct",
    "max_growth_pct",
}


def _source_row(d: DataSource) -> dict:
    row = {f: getattr(d, f) for f in SOURCE_FIELDS}
    row.update(
        id=d.pk,
        reachable=d.last_ok,
        last_error=d.last_error,
        last_checked_at=d.last_checked_at,
        last_changed_at=d.last_changed_at,
        update_available=d.update_available,
        consecutive_failures=d.consecutive_failures,
        terms_confirmed=d.terms_confirmed_at is not None,
        last_imported_at=d.last_imported_at,
        last_import_result=d.last_import_result,
        record_count=d.record_count,
        can_import=bool(d.importer),
        publication_state=d.publication_state,
        mapping_approved_at=d.mapping_approved_at,
        first_batch_approved_at=d.first_batch_approved_at,
        held_reason=d.held_reason,
    )
    return row


def _apply_source(d: DataSource, data: dict) -> list[str]:
    changed = []
    for f in SOURCE_FIELDS:
        if f not in data:
            continue
        v = data[f]
        if f in SOURCE_BOOLS:
            v = bool(v)
        elif f in SOURCE_INTS:
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValidationError({f: "Must be a whole number."}) from None
        else:
            v = str(v).strip()
        if getattr(d, f) != v:
            setattr(d, f, v)
            changed.append(f)
    return changed


@untyped_schema
@api_view(["GET", "POST"])
@permission_classes([IsAdminRole])
def sources(request):
    if request.method == "GET":
        return Response({"results": [_source_row(d) for d in DataSource.objects.all()]})
    d = DataSource()
    try:
        _apply_source(d, request.data)
        d.full_clean()
    except ValidationError as exc:
        return Response({"detail": "; ".join(exc.messages)}, status=http.HTTP_400_BAD_REQUEST)
    d.save()
    AuditLog.objects.create(
        actor=request.user,
        action="source_created",
        object_type=d._meta.label,
        object_id=str(d.pk),
        after={f: str(getattr(d, f)) for f in SOURCE_FIELDS if f != "notes"},
    )
    return Response(_source_row(d), status=http.HTTP_201_CREATED)


@untyped_schema
@api_view(["PATCH"])
@permission_classes([IsAdminRole])
def source_update(request, pk):
    d = DataSource.objects.filter(pk=pk).first()
    if d is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    before = {f: str(getattr(d, f)) for f in SOURCE_FIELDS}
    try:
        changed = _apply_source(d, request.data)
        d.full_clean()
    except ValidationError as exc:
        return Response({"detail": "; ".join(exc.messages)}, status=http.HTTP_400_BAD_REQUEST)
    d.save()
    if changed:
        AuditLog.objects.create(
            actor=request.user,
            action="source_edited",
            object_type=d._meta.label,
            object_id=str(d.pk),
            # credentials_ref is only a variable name, but never log values of secrets either way.
            before={f: before[f] for f in changed},
            after={f: str(getattr(d, f)) for f in changed},
        )
    return Response(_source_row(d))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAdminRole])
def source_action(request, pk, action):
    from apps.automation import datasources as ds
    from apps.automation import publishing

    d = DataSource.objects.filter(pk=pk).first()
    if d is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    if action in ("pause", "resume"):
        d.paused = action == "pause"
        d.save(update_fields=["paused", "updated_at"])
    elif action in ("check", "retry"):
        if d.paused:
            return Response({"detail": "Source is paused."}, status=http.HTTP_409_CONFLICT)
        ds.check_source(d)
    elif action == "confirm-terms":
        ds.confirm_terms(d, request.user)
    elif action == "approve-mapping":
        publishing.approve_mapping(d, request.user)
    elif action == "validate":
        report = publishing.validate_registrations(d).as_dict()
        return Response({**_source_row(d), "validation": report})
    elif action == "approve-first-batch":
        try:
            result = publishing.approve_first_batch(d, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=http.HTTP_409_CONFLICT)
        d.refresh_from_db()
        return Response({**_source_row(d), **result})
    elif action == "release-hold":
        publishing.release_hold(d, request.user)
    elif action == "import":
        try:
            result = ds.sync_source(d)
        except ds.SyncError as exc:
            return Response({"detail": str(exc)}, status=http.HTTP_409_CONFLICT)
        d.refresh_from_db()
        AuditLog.objects.create(
            actor=request.user,
            action="source_import_run",
            object_type=d._meta.label,
            object_id=str(d.pk),
            after={"result": str(result)[:300]},
        )
        return Response(_source_row(d))
    else:
        return Response({"detail": "Unknown action."}, status=http.HTTP_404_NOT_FOUND)
    d.refresh_from_db()
    AuditLog.objects.create(
        actor=request.user,
        action=f"source_{action.replace('-', '_')}",
        object_type=d._meta.label,
        object_id=str(d.pk),
    )
    return Response(_source_row(d))


# ---------- search misses ----------


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def search_misses(request):
    from apps.search.misses import top_misses

    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
    except ValueError:
        limit = 50
    include = request.query_params.get("resolved") == "1"
    return Response({"results": top_misses(limit, include)})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def search_miss_resolve(request, pk):
    from apps.search.models import SearchMiss

    miss = SearchMiss.objects.filter(pk=pk).first()
    if miss is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    miss.resolved = bool(request.data.get("resolved", True))
    miss.save(update_fields=["resolved", "last_seen"])
    return Response({"id": miss.pk, "resolved": miss.resolved})


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def country_coverage(request):
    from apps.countries.coverage import coverage_report

    return Response({"results": coverage_report()})


# ---------- review pipeline: triage, bulk actions, repairs ----------


def _params(request) -> dict:
    return {k: v for k, v in request.query_params.items()}


def _int(value, default=1, cap=100000) -> int:
    try:
        return max(1, min(int(value), cap))
    except (TypeError, ValueError):
        return default


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def pipeline_overview(request):
    return Response(triage.overview())


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def pipeline_facets(request):
    return Response(triage.facets())


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def pipeline_groups(request):
    by = request.query_params.get("by", "type")
    if by not in triage.GROUPS:
        return Response({"detail": "Unknown grouping."}, status=http.HTTP_400_BAD_REQUEST)
    return Response({"by": by, "groups": triage.groups(_params(request), by)})


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def pipeline_items(request):
    size = _int(request.query_params.get("page_size"), triage.PAGE_SIZE, 100)
    return Response(
        triage.items(_params(request), _int(request.query_params.get("page"), 1, 1000), size)
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def pipeline_search(request):
    """Unified search over all records: name, ID, source, country or category."""
    params = {"scope": "all", **_params(request)}
    return Response(triage.items(params, _int(request.query_params.get("page"), 1, 1000)))


def _targets(request) -> tuple[list[tuple[str, int]], bool]:
    """Selected records: explicit `ids` or everything matching `filter`. (targets, truncated)."""
    cap = bulk.MAX_TARGETS
    ids = request.data.get("ids")
    if isinstance(ids, list):
        out = []
        for item in ids[:cap]:
            if isinstance(item, (list, tuple)) and len(item) == 2 and str(item[1]).isdigit():
                out.append((str(item[0]), int(item[1])))
        return out, len(ids) > cap
    flt = request.data.get("filter")
    flt = flt if isinstance(flt, dict) else {}
    qs = triage.filtered({k: str(v) for k, v in flt.items()}).order_by("pk")
    rows = list(qs.values_list("model_key", "object_id")[: cap + 1])
    return [(m, i) for m, i in rows[:cap]], len(rows) > cap


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def bulk_preview(request):
    action = str(request.data.get("action", ""))
    if action not in bulk.ACTIONS:
        return Response({"detail": "Unknown action."}, status=http.HTTP_400_BAD_REQUEST)
    targets, truncated = _targets(request)
    result = bulk.preview(action, targets, request.user)
    result.pop("targets")
    result["truncated"] = truncated
    result["max_targets"] = bulk.MAX_TARGETS
    return Response(result)


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def bulk_start(request):
    action = str(request.data.get("action", ""))
    if action not in bulk.ACTIONS:
        return Response({"detail": "Unknown action."}, status=http.HTTP_400_BAD_REQUEST)
    if action == "approve_safe" and not request.user.can_approve_clinical:
        return Response(
            {"detail": "Only veterinarian reviewers or admins can approve records."},
            status=http.HTTP_403_FORBIDDEN,
        )
    targets, _ = _targets(request)
    plan = bulk.preview(action, targets, request.user)
    expected = request.data.get("expected_count")
    if expected is None or int(expected) != plan["eligible"]:
        return Response(
            {
                "detail": "The set changed since the preview. Preview again.",
                "eligible": plan["eligible"],
            },
            status=http.HTTP_409_CONFLICT,
        )
    reason = str(request.data.get("reason", ""))[:300]
    if action == "approve_safe" and not reason.strip():
        return Response(
            {"detail": "Give a reason; it is recorded in the audit log."},
            status=http.HTTP_400_BAD_REQUEST,
        )
    op = bulk.start(action, plan["targets"], request.user, reason)
    return Response(bulk.serialize(op), status=http.HTTP_201_CREATED)


def _op(pk):
    return bulk.BulkOperation.objects.filter(pk=pk).select_related("actor").first()


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def bulk_list(request):
    ops = bulk.BulkOperation.objects.select_related("actor")[:20]
    return Response({"results": [bulk.serialize(o) for o in ops]})


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def bulk_detail(request, pk):
    op = _op(pk)
    if op is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    return Response(bulk.serialize(op, with_results=True))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def bulk_step(request, pk):
    op = _op(pk)
    if op is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    if op.actor_id != request.user.pk and not request.user.is_superuser:
        return Response({"detail": "Not your operation."}, status=http.HTTP_403_FORBIDDEN)
    return Response(bulk.serialize(bulk.step(op), with_results=True))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def bulk_retry(request, pk):
    op = _op(pk)
    if op is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    new = bulk.retry_failed(op, request.user)
    return Response(bulk.serialize(new), status=http.HTTP_201_CREATED)


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def record_repair(request, model_key, pk):
    """Re-run the pipeline's preparation for one record: link sources, find images, reassess."""
    obj = services.get_record(model_key, pk)
    if obj is None:
        return Response({"detail": "Record not found."}, status=http.HTTP_404_NOT_FOUND)
    result = pipeline.prepare(obj)
    assessment.assess(obj)
    AuditLog.objects.create(
        actor=request.user,
        action="record_repaired",
        object_type=obj._meta.label,
        object_id=str(obj.pk),
        after=result,
    )
    return Response({**result, "detail": services.record_detail(model_key, pk)})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def image_retry(request, pk):
    asset = ImageAsset.objects.filter(pk=pk).first()
    if asset is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    asset = images.retry(asset)
    record = asset.content_type.get_object_for_this_type(pk=asset.object_id)
    assessment.assess(record)
    AuditLog.objects.create(
        actor=request.user,
        action="image_retried",
        object_type=record._meta.label,
        object_id=str(record.pk),
        after={"image": asset.pk, "status": asset.status, "detail": asset.status_detail},
    )
    return Response({"id": asset.pk, "status": asset.status, "status_detail": asset.status_detail})
