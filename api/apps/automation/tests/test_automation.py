import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.automation import safe_http, tasks
from apps.automation.models import Feed, JobRun, SourceHealth
from apps.opportunities.models import Job, ListingStatus, Scholarship
from apps.sources.models import Source

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Vet officer</title><link>https://example.org/jobs/1</link>
<description>&lt;p&gt;Field &amp;amp; clinic work&lt;/p&gt;</description></item>
<item><title>No link</title></item>
<item><title>Bad scheme</title><link>javascript:alert(1)</link></item>
<item><title>Second post</title><link>https://example.org/jobs/2</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom job</title>
<link href="https://example.org/a/1"/><summary>Plain summary</summary></entry></feed>"""

BOMB = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>
<rss><channel><item><title>&lol2;</title><link>https://example.org/x</link></item></channel></rss>"""


# ---------- safe_http ----------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://192.168.1.1/",
        "file:///etc/passwd",
        "ftp://example.org/",
        "http://8.8.8.8:8080/",
    ],
)
def test_unsafe_urls_are_refused(url):
    with pytest.raises(safe_http.FetchError):
        safe_http.assert_public_url(url)


def test_public_ip_literal_passes():
    safe_http.assert_public_url("https://8.8.8.8/")


# ---------- feed parsing ----------


def test_rss_and_atom_parse_and_strip_html_and_drop_bad_items():
    items = tasks.parse_feed(RSS)
    assert [i["title"] for i in items] == ["Vet officer", "Second post"]
    assert items[0]["summary"] == "Field & clinic work"
    assert tasks.parse_feed(ATOM)[0]["link"] == "https://example.org/a/1"


def test_hostile_xml_is_rejected():
    with pytest.raises(safe_http.FetchError):
        tasks.parse_feed(BOMB)
    with pytest.raises(safe_http.FetchError):
        tasks.parse_feed(b"not xml")


# ---------- feeds ----------


@pytest.fixture
def feed(db):
    call_command("seed_reference")
    return Feed.objects.create(
        name="Example jobs",
        url="https://example.org/feed.xml",
        kind="jobs",
        organization="Example Org",
        default_job_type="full_time",
        license_note="Test terms allow reuse",
        enabled=True,
    )


@pytest.fixture
def net(monkeypatch):
    state = {"robots": True, "status": 200, "body": RSS}
    monkeypatch.setattr(tasks.safe_http, "allowed_by_robots", lambda url: state["robots"])
    monkeypatch.setattr(
        tasks.safe_http, "fetch", lambda url, **kw: (state["status"], state["body"], url)
    )
    return state


def test_feed_creates_only_pending_listings_and_dedupes(feed, net):
    r = tasks.run_feed(feed)
    assert r["created"] == 2
    jobs = Job.objects.all()
    assert {j.status for j in jobs} == {ListingStatus.PENDING}
    assert Job.objects.public().count() == 0
    assert all(
        j.submitted_by.username == "feed-bot" and j.organization == "Example Org" for j in jobs
    )
    feed.refresh_from_db()
    assert feed.robots_confirmed_at is not None and "created 2" in feed.last_result
    # unchanged feed is skipped; changed feed only adds the new item
    assert tasks.run_feed(feed)["skipped"] == "feed unchanged"
    net["body"] = RSS.replace(
        b"</channel>",
        b"<item><title>New</title><link>https://example.org/jobs/3</link></item></channel>",
    )
    r = tasks.run_feed(feed)
    assert r["created"] == 1 and r["duplicates"] == 2


def test_feed_respects_disabled_license_and_robots(feed, net):
    feed.enabled = False
    feed.save()
    assert tasks.run_feed(feed)["skipped"] == "feed is disabled"
    feed.enabled, feed.license_note = True, ""
    feed.save()
    assert "licence" in tasks.run_feed(feed)["skipped"]
    feed.license_note = "ok"
    feed.save()
    net["robots"] = False
    assert "robots" in tasks.run_feed(feed)["skipped"]
    feed.refresh_from_db()
    assert feed.enabled is False and Job.objects.count() == 0  # auto-disabled, nothing fetched


def test_feed_http_error_is_recorded_not_raised(feed, net):
    net["status"] = 500
    r = tasks.run_feed(feed)
    assert "HTTP 500" in r["skipped"]
    feed.refresh_from_db()
    assert feed.last_result.startswith("failed")


def test_scholarship_feed_needs_level(feed, net):
    feed.kind, feed.default_job_type, feed.default_level = "scholarships", "", ""
    feed.save()
    assert "level" in tasks.run_feed(feed)["skipped"]
    feed.default_level = "phd"
    feed.save()
    assert tasks.run_feed(feed)["created"] == 2
    assert Scholarship.objects.filter(level="phd", status=ListingStatus.PENDING).count() == 2


# ---------- link health ----------


def test_link_check_records_ok_fail_and_skipped(db, monkeypatch):
    good = Source.objects.create(source_type="other", title="Good", url="https://good.example/a")
    bad = Source.objects.create(source_type="other", title="Bad", url="https://bad.example/a")
    blocked = Source.objects.create(
        source_type="other", title="Blocked", url="https://no.example/a"
    )
    Source.objects.create(source_type="other", title="No url", publisher="Someone")
    codes = {"good.example": 200, "bad.example": 404}
    monkeypatch.setattr(tasks.safe_http, "allowed_by_robots", lambda url: "no.example" not in url)
    monkeypatch.setattr(
        tasks.safe_http, "fetch", lambda url, **kw: (codes[url.split("/")[2]], b"", url)
    )
    result = tasks.check_source_links()
    assert result == {"checked": 3, "ok": 1, "failed": 1, "skipped": 1}
    assert SourceHealth.objects.get(source=good).ok
    b = SourceHealth.objects.get(source=bad)
    assert (
        not b.ok and b.status_code == 404 and b.error == "HTTP 404" and b.consecutive_failures == 1
    )
    assert SourceHealth.objects.get(source=blocked).ok  # skipped, not counted as broken
    tasks.check_source_links()
    assert SourceHealth.objects.get(source=bad).consecutive_failures == 2


def test_link_check_falls_back_to_get_when_head_refused(db, monkeypatch):
    Source.objects.create(source_type="other", title="S", url="https://x.example/a")
    calls = []

    def fake(url, method="GET", **kw):
        calls.append(method)
        return (405 if method == "HEAD" else 200), b"", url

    monkeypatch.setattr(tasks.safe_http, "allowed_by_robots", lambda url: True)
    monkeypatch.setattr(tasks.safe_http, "fetch", fake)
    assert tasks.check_source_links()["ok"] == 1 and calls == ["HEAD", "GET"]


def test_unreachable_source_is_a_failure_not_a_crash(db, monkeypatch):
    Source.objects.create(source_type="other", title="S", url="https://x.example/a")

    def boom(url, **kw):
        raise safe_http.FetchError("The URL points to a non-public address.")

    monkeypatch.setattr(tasks.safe_http, "allowed_by_robots", lambda url: True)
    monkeypatch.setattr(tasks.safe_http, "fetch", boom)
    assert tasks.check_source_links()["failed"] == 1
    assert "non-public" in SourceHealth.objects.get().error


# ---------- runner and cron ----------


def test_run_task_records_success_and_failure(db, monkeypatch):
    assert tasks.run_task("feeds").status == "ok"
    monkeypatch.setitem(tasks.TASKS, "feeds", lambda: 1 / 0)
    run = tasks.run_task("feeds")
    assert run.status == "failed" and "ZeroDivisionError" in run.error
    assert JobRun.objects.count() == 2


def test_cron_endpoint_requires_the_secret(db, settings):
    api = APIClient()
    settings.CRON_SECRET = ""
    assert api.get("/api/v1/cron/feeds/").status_code == 403  # disabled entirely
    settings.CRON_SECRET = "s3cret"
    assert api.get("/api/v1/cron/feeds/").status_code == 403
    assert api.get("/api/v1/cron/feeds/", HTTP_AUTHORIZATION="Bearer wrong").status_code == 403
    ok = api.get("/api/v1/cron/feeds/", HTTP_AUTHORIZATION="Bearer s3cret")
    assert ok.status_code == 200 and ok.json()["status"] == "ok"
    assert api.get("/api/v1/cron/nope/", HTTP_AUTHORIZATION="Bearer s3cret").status_code == 404
