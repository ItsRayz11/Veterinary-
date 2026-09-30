"""Automation tasks. Each is idempotent, bounded, logged as a JobRun; none publishes anything."""

import hashlib
import html
import re

from defusedxml import ElementTree
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.opportunities.models import Job, Scholarship
from apps.sources.models import Source

from . import safe_http
from .models import Feed, FeedKind, JobRun, RunStatus, SourceHealth

LINK_CHECK_LIMIT = 50
FEED_MAX_ITEMS = 30
BOT_USERNAME = "feed-bot"


def _tag(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def bot_user():
    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=BOT_USERNAME, defaults={"role": "registered"}
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


# ---------- link health ----------


def _probe(url: str) -> tuple[int | None, str]:
    if not safe_http.allowed_by_robots(url):
        return None, "skipped: robots.txt does not allow automated access"
    status, _, _ = safe_http.fetch(url, method="HEAD")
    if status in (403, 405, 501):  # some servers refuse HEAD
        try:
            status, _, _ = safe_http.fetch(url, method="GET", max_bytes=2_000_000)
        except safe_http.FetchError as exc:
            if "larger than" not in str(exc):
                raise
            status = 200
    return status, ""


def check_source_links(limit: int = LINK_CHECK_LIMIT) -> dict:
    """Check the least recently checked Source URLs; record the result per source."""
    qs = (
        Source.objects.exclude(url="").select_related("health").order_by("health__checked_at", "pk")
    )
    ok = failed = skipped = 0
    for source in qs[:limit]:
        code, error = None, ""
        try:
            code, error = _probe(source.url)
        except safe_http.FetchError as exc:
            error = str(exc)
        health, _ = SourceHealth.objects.get_or_create(
            source=source, defaults={"checked_at": timezone.now(), "ok": True}
        )
        if error.startswith("skipped"):
            skipped += 1
            health.ok, health.consecutive_failures = True, 0
        else:
            good = code is not None and 200 <= code < 400
            health.ok = good
            health.consecutive_failures = 0 if good else health.consecutive_failures + 1
            ok, failed = ok + good, failed + (not good)
            if not good and not error:
                error = f"HTTP {code}"
        health.status_code, health.error = code, error[:200]
        health.checked_at = timezone.now()
        health.save()
    return {"checked": ok + failed + skipped, "ok": ok, "failed": failed, "skipped": skipped}


# ---------- feeds ----------


def parse_feed(body: bytes) -> list[dict]:
    """RSS 2.0 or Atom to [{title, link, summary}] with tags stripped. Unsafe XML is rejected."""
    try:
        root = ElementTree.fromstring(body)
    except Exception as exc:
        raise safe_http.FetchError("The feed is not valid, safe XML.") from exc
    items = []
    for node in root.iter():
        name = node.tag.rsplit("}", 1)[-1]
        if name not in ("item", "entry"):
            continue
        fields = {}
        for child in node:
            cname = child.tag.rsplit("}", 1)[-1]
            if cname == "link":
                fields["link"] = (child.get("href") or child.text or "").strip()
            elif cname in ("title", "description", "summary") and cname not in fields:
                fields[cname] = _tag(child.text or "")
        title, link = fields.get("title", ""), fields.get("link", "")
        if title and link.lower().startswith(("http://", "https://")):
            items.append(
                {
                    "title": title[:200],
                    "link": link,
                    "summary": fields.get("description") or fields.get("summary", ""),
                }
            )
    return items[:FEED_MAX_ITEMS]


def run_feed(feed: Feed) -> dict:
    """Fetch one enabled feed and create PENDING listings for items not seen before."""
    result = {"created": 0, "duplicates": 0, "skipped": ""}

    def finish(msg: str):
        feed.last_run_at, feed.last_result = timezone.now(), msg[:300]
        feed.save(
            update_fields=[
                "enabled",
                "last_run_at",
                "last_result",
                "last_checksum",
                "robots_confirmed_at",
                "updated_at",
            ]
        )
        return result

    if not feed.enabled:
        result["skipped"] = "feed is disabled"
        return result
    try:
        feed.full_clean(exclude=["url"])
    except Exception as exc:
        result["skipped"] = "; ".join(getattr(exc, "messages", [str(exc)]))
        return finish(result["skipped"])
    if not safe_http.allowed_by_robots(feed.url):
        feed.enabled, feed.robots_confirmed_at = False, None
        result["skipped"] = "robots.txt does not allow automated access; feed disabled"
        return finish(result["skipped"])
    feed.robots_confirmed_at = timezone.now()
    try:
        status, body, _ = safe_http.fetch(feed.url)
        if status != 200:
            raise safe_http.FetchError(f"HTTP {status}")
        checksum = hashlib.sha256(body).hexdigest()
        if checksum == feed.last_checksum:
            result["skipped"] = "feed unchanged"
            return finish("unchanged")
        items = parse_feed(body)
    except safe_http.FetchError as exc:
        result["skipped"] = str(exc)
        return finish(f"failed: {exc}")
    model = Job if feed.kind == FeedKind.JOBS else Scholarship
    extra = (
        {"job_type": feed.default_job_type}
        if feed.kind == FeedKind.JOBS
        else {"level": feed.default_level, "funding": "unknown"}
    )
    bot = bot_user()
    for item in items:
        if model.objects.filter(apply_url=item["link"]).exists():
            result["duplicates"] += 1
            continue
        model.objects.create(
            title=item["title"],
            organization=feed.organization,
            country=feed.default_country,
            description=(item["summary"] or item["title"])[:3000],
            apply_url=item["link"][:1000],
            submitted_by=bot,
            **extra,
        )
        result["created"] += 1
    feed.last_checksum = checksum
    return finish(f"created {result['created']}, duplicates {result['duplicates']}")


def run_all_feeds() -> dict:
    total = {"feeds": 0, "created": 0}
    for feed in Feed.objects.filter(enabled=True):
        total["feeds"] += 1
        total["created"] += run_feed(feed)["created"]
    return total


# ---------- runner ----------

TASKS = {"link-check": check_source_links, "feeds": run_all_feeds}


def run_task(name: str) -> JobRun:
    """Run a named task and record the outcome. Unknown names raise KeyError."""
    fn = TASKS[name]
    run = JobRun.objects.create(task=name)
    try:
        run.summary = fn()
        run.status = RunStatus.OK
    except Exception as exc:  # noqa: BLE001 - recorded, never raised into the scheduler
        run.status, run.error = RunStatus.FAILED, f"{type(exc).__name__}: {exc}"[:300]
    run.finished_at = timezone.now()
    run.save()
    return run
