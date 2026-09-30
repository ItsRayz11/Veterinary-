from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.permissions import IsEditor
from apps.core.schema import untyped_schema
from apps.core.throttling import UserThrottle

from . import service
from .models import ClientError


class ErrorReportThrottle(UserThrottle):
    scope = "client_error"


@untyped_schema
@api_view(["POST"])
@authentication_classes([])  # anonymous by design: no session, so no CSRF and no identity stored
@permission_classes([AllowAny])
@throttle_classes([ErrorReportThrottle])
def report(request):
    service.record(
        message=request.data.get("message", ""),
        stack=request.data.get("stack", ""),
        url=request.data.get("url", ""),
        user_agent=request.headers.get("User-Agent", ""),
        release=request.data.get("release", ""),
    )
    return Response(status=status.HTTP_202_ACCEPTED)


@untyped_schema
@api_view(["GET"])
@permission_classes([IsEditor])
def errors(request):
    show_resolved = request.query_params.get("resolved") == "1"
    rows = ClientError.objects.filter(resolved=show_resolved)[:50]
    return Response(
        {
            "results": [
                {
                    "id": e.pk,
                    "message": e.message,
                    "stack": e.stack[:1500],
                    "path": e.path,
                    "count": e.count,
                    "first_seen": e.first_seen,
                    "last_seen": e.last_seen,
                    "release": e.release,
                }
                for e in rows
            ]
        }
    )


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def resolve(request, pk):
    updated = ClientError.objects.filter(pk=pk).update(resolved=True)
    if not updated:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response({"id": pk, "resolved": True})
