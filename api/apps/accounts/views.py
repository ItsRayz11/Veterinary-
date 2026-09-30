import time

from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.core.schema import untyped_schema
from apps.core.throttling import ClientIPMixin

from . import lockout, mfa
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class AuthThrottle(ClientIPMixin, SimpleRateThrottle):
    """Per-IP limit on register/login attempts (rate configured as 'auth' in settings)."""

    scope = "auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrfToken": get_token(request)})


@untyped_schema
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register(request):
    s = RegisterSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    user = s.save()
    login(request, user)
    return Response(
        UserSerializer(user, context={"request": request}).data, status=status.HTTP_201_CREATED
    )


@untyped_schema
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login_view(request):
    username = str(request.data.get("username", ""))
    lockout.check(username)  # 429 while the account is locked
    s = LoginSerializer(data=request.data, context={"request": request})
    try:
        s.is_valid(raise_exception=True)
    except ValidationError:
        lockout.failure(username)
        raise
    lockout.success(username)
    user = s.validated_data["user"]
    if mfa.enabled(user):
        # Password is right but the session is NOT signed in until the second factor passes.
        request.session["mfa_pending_user"] = user.pk
        request.session["mfa_pending_at"] = time.time()
        return Response({"mfa_required": True})
    login(request, user)
    return Response(UserSerializer(user, context={"request": request}).data)


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@untyped_schema
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user, context={"request": request}).data)
