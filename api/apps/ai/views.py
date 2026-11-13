from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole, IsModerator
from apps.core.crud import crud_views, simple_row
from apps.core.models import AuditLog
from apps.core.schema import untyped_schema
from apps.education.models import QuestionReport

from . import client
from .models import AIProvider, AITaskRoute, AIUsage
from .triage import triage_report


class IsAdminRole(HasRole):
    roles = frozenset({Role.ADMIN})


PROVIDER_FIELDS = [
    "kind", "enabled", "base_url", "api_key_env", "default_model", "timeout_seconds",
    "rate_limit_per_minute", "monthly_budget_usd",
]  # fmt: skip
ROUTE_FIELDS = [
    "task", "provider", "model", "fallback_provider", "fallback_model", "max_tokens", "enabled",
]  # fmt: skip


def _provider_extra(p):
    import os

    return {
        # Only whether a key is present: never the key or any part of it.
        "key_present": bool(os.environ.get(p.api_key_env)),
        "last_test_ok": p.last_test_ok,
        "last_test_at": p.last_test_at,
        "last_test_message": p.last_test_message,
        "spend_this_month_usd": str(client.month_spend(p)),
    }


providers, provider_update = crud_views(
    AIProvider, fields=PROVIDER_FIELDS, perm=IsAdminRole, name="ai_provider",
    row=simple_row(PROVIDER_FIELDS, _provider_extra), create_only=("kind",),
)  # fmt: skip
routes, route_update = crud_views(
    AITaskRoute, fields=ROUTE_FIELDS, perm=IsAdminRole, name="ai_route",
    row=simple_row(ROUTE_FIELDS), create_only=("task",),
)  # fmt: skip


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAdminRole])
def provider_test(request, pk):
    p = AIProvider.objects.filter(pk=pk).first()
    if p is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    ok, msg = client.check_connection(p)
    AuditLog.objects.create(
        actor=request.user, action="ai_provider_tested", object_type=p._meta.label,
        object_id=str(p.pk), after={"ok": ok},
    )  # fmt: skip
    return Response(_row(p) | {"detail": msg})


def _row(p):
    return simple_row(PROVIDER_FIELDS, _provider_extra)(p)


@untyped_schema
@api_view(["GET"])
@permission_classes([IsAdminRole])
def usage(request):
    start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month = AIUsage.objects.filter(at__gte=start)
    by_task = month.values("task", "model").annotate(
        calls=Count("id"),
        cost=Sum("cost_usd"),
        tokens=Sum("prompt_tokens") + Sum("completion_tokens"),
    )
    return Response(
        {
            "note": "Costs are planning estimates from token counts, not provider invoices.",
            "month_calls": month.count(),
            "month_failed": month.filter(ok=False).count(),
            "month_cost_usd": str(month.aggregate(t=Sum("cost_usd"))["t"] or Decimal("0")),
            "by_task": [
                {"task": r["task"], "model": r["model"], "calls": r["calls"],
                 "cost_usd": str(r["cost"] or 0), "tokens": r["tokens"] or 0}
                for r in by_task
            ],
            "recent": [
                {"at": u.at, "task": u.task, "model": u.model, "ok": u.ok, "error": u.error,
                 "cost_usd": str(u.cost_usd)}
                for u in AIUsage.objects.all()[:30]
            ],
        }
    )  # fmt: skip


@untyped_schema
@api_view(["GET"])
@permission_classes([IsModerator])
def report_triage(request):
    """Rule-based triage of open question reports (no AI call, nothing is changed)."""
    out = []
    reports = QuestionReport.objects.filter(resolved=False).select_related("question")[:200]
    for r in reports:
        dupes = (
            QuestionReport.objects.filter(question_id=r.question_id, resolved=False)
            .exclude(pk=r.pk)
            .count()
        )
        t = triage_report(r.message, has_citation=("http" in r.message), duplicates_open=dupes)
        out.append(
            {"id": r.pk, "question": r.question.stem[:120], "message": r.message,
             "category": t.category, "escalate": t.escalate_to_clinician, "reasons": t.reasons}
        )  # fmt: skip
    return Response({"results": out})
