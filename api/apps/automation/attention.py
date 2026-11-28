"""What needs a person right now, and the daily staff digest that says so.

Read-only apart from one piece of housekeeping (closing browser errors nobody has seen for
STALE_ERROR_DAYS). Nothing here publishes, approves or edits catalogue or clinical data.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import DataSource, JobRun, RunStatus, SourceHealth

# Every scheduled task runs once a day (api/vercel.json). A task with no run for longer than this
# has stopped firing (cron secret rotated, project paused, schedule removed).
MISSED_AFTER = timedelta(hours=26)
STALE_ERROR_DAYS = 14
BROKEN_SOURCE_FAILURES = 3


def scheduled_tasks() -> list[str]:
    from .tasks import TASKS

    return sorted(TASKS)


def missed_runs(now=None) -> list[dict]:
    """Scheduled tasks whose last run (any outcome) is older than MISSED_AFTER, or never ran."""
    now = now or timezone.now()
    out = []
    for task in scheduled_tasks():
        last = JobRun.objects.filter(task=task).order_by("-created_at").first()
        if last is None or now - last.created_at > MISSED_AFTER:
            out.append({"task": task, "last_run": last.created_at if last else None})
    return out


def failed_runs(now=None) -> list[dict]:
    """The latest run of each task, where that run failed in the last day."""
    now = now or timezone.now()
    out = []
    for task in scheduled_tasks():
        last = JobRun.objects.filter(task=task).order_by("-created_at").first()
        if last and last.status == RunStatus.FAILED and now - last.created_at <= MISSED_AFTER:
            out.append({"task": task, "error": last.error, "at": last.created_at})
    return out


def close_stale_errors(now=None, days: int = STALE_ERROR_DAYS) -> int:
    """Resolve browser errors not seen for `days`. A new occurrence reopens them
    (monitoring.service.record sets resolved=False), so nothing is lost."""
    from apps.monitoring.models import ClientError

    cutoff = (now or timezone.now()) - timedelta(days=days)
    return ClientError.objects.filter(resolved=False, last_seen__lt=cutoff).update(resolved=True)


def _pending_price_outliers() -> int:
    from apps.pricing.models import PriceSubmission, SubmissionKind, SubmissionStatus
    from apps.pricing.services import screen_submission

    pending = PriceSubmission.objects.filter(
        status=SubmissionStatus.PENDING, kind=SubmissionKind.NEW_PRICE
    ).select_related("country")[:100]
    return sum(1 for s in pending if screen_submission(s)["outlier"])


def report(now=None) -> dict:
    """Everything that needs a person, as counts plus a short ordered list of items.

    Each item names the admin panel section that resolves it, so the dashboard and the push
    digest point at the same place.
    """
    from apps.monitoring.models import ClientError
    from apps.search.models import SearchMiss

    now = now or timezone.now()
    missed = missed_runs(now)
    failed = failed_runs(now)
    broken = SourceHealth.objects.filter(
        ok=False, consecutive_failures__gte=BROKEN_SOURCE_FAILURES
    ).count()
    held = list(DataSource.objects.exclude(held_reason="").values_list("name", flat=True))
    new_errors = ClientError.objects.filter(
        resolved=False, first_seen__gte=now - timedelta(days=1)
    ).count()
    outliers = _pending_price_outliers()
    frequent_misses = SearchMiss.objects.filter(resolved=False, count__gte=3).count()

    items: list[dict] = []
    for f in failed:
        items.append(
            {
                "severity": "danger",
                "section": "automation",
                "text": f"{f['task']} failed: {f['error'] or 'no detail recorded'}",
            }
        )
    for m in missed:
        when = f"last ran {m['last_run']:%Y-%m-%d %H:%M} UTC" if m["last_run"] else "never ran"
        items.append(
            {
                "severity": "danger",
                "section": "automation",
                "text": f"{m['task']} has not run on schedule ({when})",
            }
        )
    for name in held:
        items.append(
            {
                "severity": "warn",
                "section": "sources",
                "text": f"Import from {name} is held for a person to check",
            }
        )
    if broken:
        items.append(
            {
                "severity": "warn",
                "section": "automation",
                "text": f"{broken} source link(s) failed {BROKEN_SOURCE_FAILURES}+ checks in a row",
            }
        )
    if outliers:
        items.append(
            {
                "severity": "warn",
                "section": "prices",
                "text": f"{outliers} price submission(s) far from published prices",
            }
        )
    if new_errors:
        items.append(
            {
                "severity": "warn",
                "section": "errors",
                "text": f"{new_errors} new browser error(s) in the last day",
            }
        )
    if frequent_misses:
        items.append(
            {
                "severity": "info",
                "section": "misses",
                "text": f"{frequent_misses} failed search(es) searched 3+ times",
            }
        )
    return {
        "generated_at": now,
        "missed_runs": missed,
        "failed_runs": failed,
        "broken_sources": broken,
        "held_syncs": held,
        "new_errors": new_errors,
        "price_outliers": outliers,
        "frequent_misses": frequent_misses,
        "items": items,
    }


def _staff_recipients():
    from apps.accounts.roles import STAFF_ROLES

    User = get_user_model()
    return User.objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(role__in=STAFF_ROLES)
    )


def staff_digest(now=None) -> dict:
    """Daily task: tidy stale errors, then push one short digest to staff if anything needs them.

    Push only reaches staff who turned notifications on (Account page); the same list is always on
    the admin panel dashboard. Quiet days send nothing, and informational items alone (such as
    frequent failed searches) never trigger a notification.
    """
    from apps.push import service as push

    closed = close_stale_errors(now)
    rep = report(now)
    items = rep["items"]
    sent = 0
    if any(i["severity"] != "info" for i in items):
        title = f"VetRef: {len(items)} item{'s' if len(items) != 1 else ''} need attention"
        body = "; ".join(i["text"] for i in items[:2])
        for user in _staff_recipients():
            sent += push.notify(user, title, body, "/admin-panel")
    return {"items": len(items), "notified_devices": sent, "errors_closed": closed}
