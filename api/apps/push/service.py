"""Web push: store subscriptions and send short notifications.

The endpoint is a URL the browser gives us and our server later calls, so it is restricted to the
known push services (otherwise a user could point the server at internal addresses). Payloads
carry only a title, one line and a same-site path: no personal or clinical data.
"""

import json
import logging
from urllib.parse import urlparse

from django.conf import settings
from pywebpush import WebPushException, webpush

from .models import PushSubscription

log = logging.getLogger(__name__)

MAX_PER_USER = 10
SEND_TIMEOUT = 5
# Hosts (or parent domains) of the push services run by the browser vendors.
ALLOWED_PUSH_HOSTS = (
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "push.apple.com",
    "notify.windows.com",
)


def enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def valid_endpoint(url: str) -> bool:
    try:
        parsed = urlparse(url or "")
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or port not in (None, 443):
        return False
    if parsed.username or parsed.password:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_PUSH_HOSTS)


def subscribe(user, endpoint: str, p256dh: str, auth: str, user_agent: str = "") -> bool:
    """Save a subscription. Returns False when the input is not acceptable."""
    if not (valid_endpoint(endpoint) and 0 < len(p256dh) <= 200 and 0 < len(auth) <= 100):
        return False
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": user, "p256dh": p256dh, "auth": auth, "user_agent": user_agent[:200]},
    )
    # Keep the newest few per user so the table cannot grow without limit.
    keep = list(
        PushSubscription.objects.filter(user=user)
        .order_by("-created_at", "-pk")
        .values_list("pk", flat=True)[:MAX_PER_USER]
    )
    PushSubscription.objects.filter(user=user).exclude(pk__in=keep).delete()
    return True


def unsubscribe(user, endpoint: str) -> int:
    deleted, _ = PushSubscription.objects.filter(user=user, endpoint=endpoint).delete()
    return deleted


def _send_one(sub: PushSubscription, payload: str) -> None:
    webpush(
        subscription_info={
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        },
        data=payload,
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims={"sub": settings.VAPID_SUBJECT},
        ttl=86400,
        timeout=SEND_TIMEOUT,
    )


def notify(user, title: str, body: str, path: str = "/") -> int:
    """Best-effort notification to all of a user's devices. Returns how many were delivered.

    Never raises: a failed push must not break the action that triggered it. Subscriptions the
    push service reports as gone (404/410) are removed.
    """
    if not enabled() or not path.startswith("/") or path.startswith("//"):
        return 0
    payload = json.dumps({"title": title[:80], "body": body[:160], "url": path})
    sent = 0
    for sub in PushSubscription.objects.filter(user=user):
        try:
            _send_one(sub, payload)
            sent += 1
        except WebPushException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code in (404, 410):
                sub.delete()
            else:
                log.warning("push failed (%s)", code)
        except Exception:  # network errors, bad keys: never break the caller
            log.warning("push failed", exc_info=True)
    return sent
