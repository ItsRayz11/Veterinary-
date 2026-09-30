"""Two-factor authentication (TOTP, RFC 6238) for accounts, mandatory for staff in production.

Design choices:
- The shared secret is stored encrypted (Fernet). Set MFA_ENCRYPTION_KEY to a dedicated key; if it
  is unset the key is derived from SECRET_KEY, which means rotating SECRET_KEY would make every
  enrolled secret unreadable, so set the dedicated key before enrolling real reviewers.
- A code can be used once (replay protection through the last accepted time step).
- Recovery codes are random, shown once, and stored only as keyed hashes.
- Wrong codes count towards the same account lockout as passwords.
"""

import base64
import hashlib
import hmac
import secrets
import time

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import RecoveryCode, Role, TotpDevice

ISSUER = "VetRef"
STEP_SECONDS = 30
WINDOW = 1  # accept the previous and next step to tolerate clock drift
RECOVERY_CODES = 10
STAFF_ROLES = frozenset({Role.REVIEWER, Role.VET_REVIEWER, Role.EDITOR, Role.MODERATOR, Role.ADMIN})


class MFARequired(PermissionDenied):
    """Raised for staff actions when two-factor is required but this session has not passed it."""

    default_code = "mfa_required"
    default_detail = (
        "Two-factor authentication is required for staff. Set it up in your account, "
        "then sign in again."
    )


def is_staff_user(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.is_staff or user.role in STAFF_ROLES)
    )


def required_for(user) -> bool:
    return bool(getattr(settings, "REQUIRE_STAFF_MFA", False)) and is_staff_user(user)


def session_passed(request) -> bool:
    return bool(request.session.get("mfa_verified"))


def enabled(user) -> bool:
    """Fresh from the database: a cached related object would go stale after disabling."""
    if not user.is_authenticated:
        return False
    return TotpDevice.objects.filter(user=user, confirmed_at__isnull=False).exists()


def _fernet() -> Fernet:
    key = getattr(settings, "MFA_ENCRYPTION_KEY", "")
    if key:
        return Fernet(key.encode("utf-8"))
    derived = hashlib.sha256(f"vetref-mfa|{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def _encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def _decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None  # wrong key: treated as "cannot verify", never as a match


def _hash_code(code: str) -> str:
    key = f"vetref-recovery|{settings.SECRET_KEY}".encode()
    return hmac.new(key, code.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalise(code: str) -> str:
    return "".join(str(code).split()).replace("-", "").lower()


def begin_setup(user) -> dict:
    """Create (or restart) an unconfirmed device and return what the authenticator app needs."""
    if enabled(user):
        raise ValueError("Two-factor authentication is already on for this account.")
    secret = pyotp.random_base32()
    TotpDevice.objects.update_or_create(
        user=user,
        defaults={"secret": _encrypt(secret), "confirmed_at": None, "last_used_step": 0},
    )
    uri = pyotp.TOTP(secret, interval=STEP_SECONDS).provisioning_uri(
        name=user.username, issuer_name=ISSUER
    )
    return {"secret": secret, "otpauth_uri": uri}


def _accepted_step(device: TotpDevice, code: str, now: float | None = None) -> int | None:
    secret = _decrypt(device.secret)
    if secret is None or not (code.isdigit() and len(code) == 6):
        return None
    totp = pyotp.TOTP(secret, interval=STEP_SECONDS)
    current = int((now if now is not None else time.time()) // STEP_SECONDS)
    for step in range(current - WINDOW, current + WINDOW + 1):
        if hmac.compare_digest(totp.generate_otp(step), code) and step > device.last_used_step:
            return step
    return None


def _use_step(device: TotpDevice, step: int) -> bool:
    """Record the step atomically; False if a concurrent request already used it."""
    return (
        TotpDevice.objects.filter(pk=device.pk, last_used_step__lt=step).update(last_used_step=step)
        == 1
    )


def _new_recovery_codes(user) -> list[str]:
    user.recovery_codes.all().delete()
    codes = [secrets.token_hex(5) for _ in range(RECOVERY_CODES)]  # 40 bits each, single use
    RecoveryCode.objects.bulk_create(
        [RecoveryCode(user=user, code_hash=_hash_code(c)) for c in codes]
    )
    return [f"{c[:5]}-{c[5:]}" for c in codes]


def confirm_setup(user, code: str) -> list[str] | None:
    """Activate the device when the code from the app is right; returns the recovery codes."""
    device = getattr(user, "totp_device", None)
    if device is None or device.confirmed_at:
        return None
    step = _accepted_step(device, _normalise(code))
    if step is None or not _use_step(device, step):
        return None
    device.confirmed_at = timezone.now()
    device.save(update_fields=["confirmed_at"])
    return _new_recovery_codes(user)


def verify(user, code: str) -> bool:
    """A current authenticator code (once) or an unused recovery code."""
    device = getattr(user, "totp_device", None)
    if device is None or not device.confirmed_at:
        return False
    code = _normalise(code)
    if code.isdigit() and len(code) == 6:
        step = _accepted_step(device, code)
        return step is not None and _use_step(device, step)
    if len(code) == 10:
        used = RecoveryCode.objects.filter(
            user=user, code_hash=_hash_code(code), used_at__isnull=True
        ).update(used_at=timezone.now())
        return used == 1
    return False


def disable(user, code: str) -> bool:
    if not verify(user, code):
        return False
    TotpDevice.objects.filter(user=user).delete()
    user.recovery_codes.all().delete()
    return True


def regenerate_recovery_codes(user, code: str) -> list[str] | None:
    return _new_recovery_codes(user) if verify(user, code) else None


def remaining_recovery_codes(user) -> int:
    return user.recovery_codes.filter(used_at__isnull=True).count()
