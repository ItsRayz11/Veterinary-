"""Per-account sign-in lockout, on top of the per-IP throttle.

The IP throttle cannot stop many addresses guessing one password. After too many failed attempts
for a username the account refuses sign-ins for a while. Counters are keyed by a hash of the
normalised username whether or not the account exists, so a lock reveals nothing about which
usernames are real. Trade-off, accepted on purpose: someone can lock a known username out for
`LOGIN_LOCK_SECONDS`; staff are additionally protected by MFA, and the lock expires by itself.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import Throttled

from apps.core.models import AuditLog


def _digest(username: str) -> str:
    return hashlib.sha256(username.strip().lower().encode("utf-8")).hexdigest()[:32]


def _keys(username: str) -> tuple[str, str]:
    d = _digest(username)
    return f"login-fail:{d}", f"login-lock:{d}"


def _limits() -> tuple[int, int]:
    return (
        int(getattr(settings, "LOGIN_MAX_FAILURES", 8)),
        int(getattr(settings, "LOGIN_LOCK_SECONDS", 900)),
    )


def check(username: str) -> None:
    """Raise Throttled (HTTP 429) if this username is currently locked."""
    _, lock_key = _keys(username)
    if cache.get(lock_key):
        _, seconds = _limits()
        minutes = max(1, round(seconds / 60))
        raise Throttled(
            wait=seconds,
            detail=(
                f"Too many failed sign-in attempts. Try again in about {minutes} minutes, "
                "or reset your password."
            ),
        )


def failure(username: str) -> None:
    """Count a failed attempt; lock the account when the limit is reached."""
    fail_key, lock_key = _keys(username)
    max_failures, seconds = _limits()
    cache.add(fail_key, 0, timeout=seconds)  # the window is as long as the lock
    try:
        count = cache.incr(fail_key)
    except ValueError:  # expired between add and incr
        cache.set(fail_key, 1, timeout=seconds)
        count = 1
    if count >= max_failures:
        cache.set(lock_key, True, timeout=seconds)
        cache.delete(fail_key)
        AuditLog.objects.create(
            actor=None,
            action="login_locked",
            object_type="accounts.User",
            object_id=_digest(username)[:16],
            after={"failures": count, "lock_seconds": seconds},
        )


def success(username: str) -> None:
    fail_key, _ = _keys(username)
    cache.delete(fail_key)
