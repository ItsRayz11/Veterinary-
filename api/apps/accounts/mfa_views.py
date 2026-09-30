"""Two-factor authentication endpoints (see mfa.py for the rules)."""

import time

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.schema import untyped_schema

from . import lockout, mfa
from .serializers import UserSerializer
from .views import AuthThrottle

PENDING_SECONDS = 300
BAD_CODE = "That code is not right. Try the next code from your app, or a recovery code."


def _code(request) -> str:
    """The submitted code, from an API body or from the admin page's HTML form."""
    data = request.data if hasattr(request, "data") else request.POST
    return str(data.get("code", ""))


def _limited(user):
    """Wrong codes count towards the same lockout as passwords (429 while locked)."""
    lockout.check(f"mfa:{user.pk}")


def _status(request) -> dict:
    user = request.user
    return {
        "enabled": mfa.enabled(user),
        "required": mfa.required_for(user),
        "verified": mfa.session_passed(request),
        "recovery_codes_left": mfa.remaining_recovery_codes(user) if mfa.enabled(user) else 0,
    }


@untyped_schema
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mfa_status(request):
    return Response(_status(request))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def mfa_setup(request):
    try:
        return Response(mfa.begin_setup(request.user))
    except ValueError as exc:
        raise ValidationError({"detail": str(exc)}) from exc


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def mfa_confirm(request):
    _limited(request.user)
    codes = mfa.confirm_setup(request.user, _code(request))
    if codes is None:
        lockout.failure(f"mfa:{request.user.pk}")
        raise ValidationError({"code": BAD_CODE})
    lockout.success(f"mfa:{request.user.pk}")
    request.session["mfa_verified"] = True  # they just proved they hold the device
    return Response({"recovery_codes": codes, **_status(request)})


@untyped_schema
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def mfa_verify(request):
    """Second step of sign-in: the password step left a pending user in the session."""
    pk = request.session.get("mfa_pending_user")
    started = request.session.get("mfa_pending_at", 0)
    user = get_user_model().objects.filter(pk=pk, is_active=True).first() if pk else None
    if user is None or time.time() - started > PENDING_SECONDS:
        request.session.pop("mfa_pending_user", None)
        raise ValidationError({"detail": "Your sign-in expired. Enter your password again."})
    _limited(user)
    if not mfa.verify(user, _code(request)):
        lockout.failure(f"mfa:{user.pk}")
        raise ValidationError({"code": BAD_CODE})
    lockout.success(f"mfa:{user.pk}")
    login(request, user)
    request.session["mfa_verified"] = True
    request.session.pop("mfa_pending_user", None)
    request.session.pop("mfa_pending_at", None)
    return Response(UserSerializer(user, context={"request": request}).data)


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def mfa_disable(request):
    if mfa.required_for(request.user):
        raise ValidationError({"detail": "Staff accounts must keep two-factor authentication on."})
    _limited(request.user)
    if not mfa.disable(request.user, _code(request)):
        lockout.failure(f"mfa:{request.user.pk}")
        raise ValidationError({"code": BAD_CODE})
    lockout.success(f"mfa:{request.user.pk}")
    request.session["mfa_verified"] = False
    return Response(_status(request))


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthThrottle])
def mfa_recovery(request):
    _limited(request.user)
    codes = mfa.regenerate_recovery_codes(request.user, _code(request))
    if codes is None:
        lockout.failure(f"mfa:{request.user.pk}")
        raise ValidationError({"code": BAD_CODE})
    lockout.success(f"mfa:{request.user.pk}")
    return Response({"recovery_codes": codes, **_status(request)}, status=status.HTTP_200_OK)


# ---- server-rendered page used to reach the Django admin (which has its own login form) ----


def _safe_next(request) -> str:
    target = request.GET.get("next") or request.POST.get("next") or "/"
    ok = url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()})
    return target if ok else "/"


@login_required(login_url="/admin/login/")
def mfa_admin_page(request):
    """Enrol or verify two-factor for a session that signed in through the Django admin form."""
    user, ctx = request.user, {"next": _safe_next(request), "error": "", "recovery_codes": None}
    if mfa.session_passed(request) and request.method == "GET":
        return HttpResponseRedirect(ctx["next"])
    if mfa.enabled(user):
        ctx["mode"] = "verify"
        if request.method == "POST":
            try:
                _limited(user)
            except Exception:  # noqa: BLE001 - shown as text, never a stack trace
                ctx["error"] = "Too many wrong codes. Try again later."
            else:
                if mfa.verify(user, _code(request)):
                    lockout.success(f"mfa:{user.pk}")
                    request.session["mfa_verified"] = True
                    return HttpResponseRedirect(ctx["next"])
                lockout.failure(f"mfa:{user.pk}")
                ctx["error"] = BAD_CODE
    else:
        ctx["mode"] = "setup"
        device = getattr(user, "totp_device", None)
        if request.method == "POST" and device is not None:
            codes = mfa.confirm_setup(user, _code(request))
            if codes:
                request.session["mfa_verified"] = True
                ctx.update(mode="done", recovery_codes=codes)
            else:
                ctx["error"] = BAD_CODE
        if ctx["mode"] == "setup":
            if device is None or request.method == "GET":
                ctx.update(mfa.begin_setup(user))
            else:
                ctx["secret"] = mfa._decrypt(device.secret)
    return render(request, "accounts/mfa_admin.html", ctx)
