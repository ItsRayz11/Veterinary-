"""Failure modes of outbound fetching: nothing may escape as anything but FetchError, and one bad
item must never stop a whole batch."""

import http.client

import pytest

from apps.automation import safe_http, tasks
from apps.automation.models import Feed, SourceHealth
from apps.sources.models import Source


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org:99999/",  # port out of range (ValueError in urlparse)
        "http://[::1/",  # malformed IPv6 literal
        "http://[fe80::1%25eth0]/",  # IPv6 with a zone id
        "http://",  # no host
        "http://exa mple.org/",  # space in host
    ],
)
def test_malformed_urls_are_fetch_errors_never_other_exceptions(url):
    with pytest.raises(safe_http.FetchError):
        safe_http.assert_public_url(url)
    with pytest.raises(safe_http.FetchError):
        safe_http.fetch(url)


class FakeResponse:
    status = 200

    def __init__(self, chunks, on_read=None):
        self._chunks, self._on_read = list(chunks), on_read

    def read(self, n=-1):
        if self._on_read:
            self._on_read()
        return self._chunks.pop(0) if self._chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.timeouts = result, error, []

    def open(self, req, timeout=None):
        self.timeouts.append(timeout)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setattr(safe_http, "assert_public_url", lambda url: None)


@pytest.mark.parametrize(
    "error",
    [
        http.client.BadStatusLine("garbage"),
        http.client.IncompleteRead(b"x"),
        http.client.LineTooLong("status line"),
        ValueError("unknown url type"),
        ConnectionResetError("reset"),
    ],
)
def test_servers_that_do_not_speak_http_become_fetch_errors(public, monkeypatch, error):
    monkeypatch.setattr(safe_http, "_opener", FakeOpener(error=error))
    with pytest.raises(safe_http.FetchError, match="Could not fetch"):
        safe_http.fetch("https://example.org/")


def test_expired_deadline_fails_before_any_network_call(public, monkeypatch):
    opener = FakeOpener(result=FakeResponse([b"x"]))
    monkeypatch.setattr(safe_http, "_opener", opener)
    monkeypatch.setattr(safe_http.time, "monotonic", lambda: 100.0)
    with pytest.raises(safe_http.FetchError, match="Timed out"):
        safe_http.fetch("https://example.org/", deadline=99.0)
    assert opener.timeouts == []


def test_step_timeout_never_exceeds_what_is_left_of_the_deadline(public, monkeypatch):
    opener = FakeOpener(result=FakeResponse([b"ok"]))
    monkeypatch.setattr(safe_http, "_opener", opener)
    monkeypatch.setattr(safe_http.time, "monotonic", lambda: 100.0)
    safe_http.fetch("https://example.org/", timeout=10, deadline=102.0)
    assert opener.timeouts == [2.0]  # 10 s allowed per step, but only 2 s of budget remain


def test_a_slow_body_is_cut_off_by_the_overall_deadline(public, monkeypatch):
    clock = {"now": 0.0}

    def slow_read():
        clock["now"] += 3.0  # each chunk takes 3 "seconds"

    monkeypatch.setattr(safe_http.time, "monotonic", lambda: clock["now"])
    opener = FakeOpener(result=FakeResponse([b"a" * 10] * 50, on_read=slow_read))
    monkeypatch.setattr(safe_http, "_opener", opener)
    with pytest.raises(safe_http.FetchError, match="Timed out"):
        safe_http.fetch("https://example.org/", deadline=8.0)


def test_oversized_body_is_refused(public, monkeypatch):
    monkeypatch.setattr(
        safe_http, "_opener", FakeOpener(result=FakeResponse([b"x" * 200_000, b"x" * 200_000]))
    )
    with pytest.raises(safe_http.FetchError, match="larger than"):
        safe_http.fetch("https://example.org/", max_bytes=300_000)


# ---------- one bad item never stops the batch ----------


def test_link_check_survives_an_unexpected_error_and_still_checks_the_rest(db, monkeypatch):
    bad = Source.objects.create(source_type="other", title="Bad", url="https://bad.example/a")
    good = Source.objects.create(source_type="other", title="Good", url="https://good.example/a")

    def probe(url, cache):
        if "bad" in url:
            raise ValueError("boom")
        return 200, ""

    monkeypatch.setattr(tasks, "_probe", probe)
    result = tasks.check_source_links()
    assert result["failed"] == 1 and result["ok"] == 1
    assert "Unexpected error: ValueError" in SourceHealth.objects.get(source=bad).error
    assert SourceHealth.objects.get(source=good).ok


def test_a_crashing_feed_is_recorded_and_does_not_starve_the_others(db, monkeypatch):
    def make(name):
        return Feed.objects.create(
            name=name,
            url=f"https://{name}.example/feed.xml",
            kind="jobs",
            organization=name,
            default_job_type="full_time",
            license_note="ok",
            enabled=True,
        )

    first = make("first")
    make("second")
    ran = []

    def run_feed(feed):
        ran.append(feed.name)
        if feed.name == "first":
            raise RuntimeError("boom")
        return {"created": 3}

    monkeypatch.setattr(tasks, "run_feed", run_feed)
    summary = tasks.run_all_feeds()
    assert ran == ["first", "second"] and summary["created"] == 3
    first.refresh_from_db()
    assert first.last_run_at is not None and "RuntimeError" in first.last_result
    # the crashed feed no longer sorts ahead of the never-run ones forever
    ran.clear()
    tasks.run_all_feeds()
    assert ran == ["second", "first"]  # never-run first; the crashed one now has a timestamp
