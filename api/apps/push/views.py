from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.schema import untyped_schema

from . import service


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def config(request):
    on = service.enabled()
    return Response({"enabled": on, "public_key": settings.VAPID_PUBLIC_KEY if on else ""})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def subscribe(request):
    if not service.enabled():
        return Response(
            {"detail": "Notifications are not enabled."}, status=status.HTTP_404_NOT_FOUND
        )
    data = request.data if isinstance(request.data, dict) else {}
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    endpoint, p256dh, auth = data.get("endpoint"), keys.get("p256dh"), keys.get("auth")
    if not all(isinstance(v, str) for v in (endpoint, p256dh, auth)) or not service.subscribe(
        request.user, endpoint, p256dh, auth, request.headers.get("User-Agent", "")
    ):
        return Response({"detail": "Invalid subscription."}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"subscribed": True}, status=status.HTTP_201_CREATED)


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unsubscribe(request):
    endpoint = request.data.get("endpoint") if isinstance(request.data, dict) else None
    if isinstance(endpoint, str):
        service.unsubscribe(request.user, endpoint)
    return Response({"subscribed": False})
