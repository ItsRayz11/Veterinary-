"""Client error intake: bounded, deduplicated and scrubbed."""

import hashlib
import re
from urllib.parse import urlparse

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import ClientError

MESSAGE_MAX = 500
STACK_MAX = 4000
UA_MAX = 200
PATH_MAX = 300
# Things that must never be stored: long tokens, emails, and numeric ids inside paths/messages.
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TOKEN = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")


def scrub(text: str) -> str:
    return TOKEN.sub("[token]", EMAIL.sub("[email]", text or ""))


def clean_path(url: str) -> str:
    """Path only (no query string, fragment or host), so ids in query parameters are dropped."""
    try:
        return urlparse(url or "").path[:PATH_MAX]
    except ValueError:
        return ""


def fingerprint(message: str, stack: str, path: str) -> str:
    first_frame = next((line.strip() for line in stack.splitlines()[1:2]), "")
    basis = "|".join([re.sub(r"\d+", "N", message), re.sub(r"\d+", "N", first_frame), path])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def record(
    *, message: str, stack: str = "", url: str = "", user_agent: str = "", release: str = ""
):
    """Store one occurrence; returns the ClientError or None when the report is empty."""
    message = scrub(str(message).strip())[:MESSAGE_MAX]
    if not message:
        return None
    stack = scrub(str(stack))[:STACK_MAX]
    path = clean_path(str(url))
    fp = fingerprint(message, stack, path)
    now = timezone.now()
    updated = ClientError.objects.filter(fingerprint=fp).update(
        count=F("count") + 1, last_seen=now, resolved=False
    )
    if not updated:
        try:
            with transaction.atomic():
                ClientError.objects.create(
                    fingerprint=fp,
                    message=message,
                    stack=stack,
                    path=path,
                    user_agent=str(user_agent)[:UA_MAX],
                    release=str(release)[:60],
                    first_seen=now,
                    last_seen=now,
                )
        except IntegrityError:  # two reports of a new error arrived together
            ClientError.objects.filter(fingerprint=fp).update(count=F("count") + 1, last_seen=now)
    return ClientError.objects.get(fingerprint=fp)
