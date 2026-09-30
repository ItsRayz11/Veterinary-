import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.schema import untyped_schema

from .tasks import TASKS, run_task


@untyped_schema
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def cron(request, task):
    """Called by the scheduler (Vercel Cron sends `Authorization: Bearer $CRON_SECRET`)."""
    secret = getattr(settings, "CRON_SECRET", "")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not secret or not hmac.compare_digest(supplied.encode(), secret.encode()):
        return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
    if task not in TASKS:
        return Response({"detail": "Unknown task."}, status=status.HTTP_404_NOT_FOUND)
    run = run_task(task)
    code = status.HTTP_200_OK if run.status == "ok" else status.HTTP_500_INTERNAL_SERVER_ERROR
    return Response({"task": run.task, "status": run.status, "summary": run.summary}, status=code)
