from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.automation import attention, images
from apps.automation.models import (
    DataSource,
    ImageAsset,
    ImageStatus,
    JobRun,
    RunStatus,
)
from apps.automation.tasks import TASKS
from apps.monitoring import service as monitoring
from apps.monitoring.models import ClientError

pytestmark = pytest.mark.django_db


def ran(task, hours_ago=1, status=RunStatus.OK, error=""):
    run = JobRun.objects.create(task=task, status=status, error=error)
    JobRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(hours=hours_ago))
    return run


def all_ran_recently():
    for task in TASKS:
        ran(task)


def test_tasks_that_never_ran_or_stopped_running_are_missed():
    assert {m["task"] for m in attention.missed_runs()} == set(TASKS)
    all_ran_recently()
    assert attention.missed_runs() == []
    ran("feeds", hours_ago=30)  # an older run does not hide a recent one
    assert attention.missed_runs() == []
    JobRun.objects.filter(task="feeds").update(created_at=timezone.now() - timedelta(hours=30))
    missed = attention.missed_runs()
    assert [m["task"] for m in missed] == ["feeds"] and missed[0]["last_run"]


def test_only_the_latest_failed_run_of_a_task_is_reported():
    all_ran_recently()
    ran("link-check", hours_ago=0, status=RunStatus.FAILED, error="TimeoutError: slow")
    failed = attention.failed_runs()
    assert [(f["task"], f["error"]) for f in failed] == [("link-check", "TimeoutError: slow")]
    ran("link-check", hours_ago=0)  # fixed on the next run
    JobRun.objects.filter(task="link-check", status=RunStatus.OK).update(created_at=timezone.now())
    assert attention.failed_runs() == []


def test_stale_errors_close_and_a_new_occurrence_reopens_them():
    old = monitoring.record(message="TypeError: old", url="/a")
    fresh = monitoring.record(message="TypeError: fresh", url="/b")
    ClientError.objects.filter(pk=old.pk).update(last_seen=timezone.now() - timedelta(days=20))
    assert attention.close_stale_errors() == 1
    old.refresh_from_db()
    fresh.refresh_from_db()
    assert old.resolved and not fresh.resolved
    monitoring.record(message="TypeError: old", url="/a")
    old.refresh_from_db()
    assert not old.resolved


def test_report_lists_each_problem_with_the_section_that_fixes_it():
    all_ran_recently()
    ran("feeds", hours_ago=0, status=RunStatus.FAILED, error="boom")
    DataSource.objects.filter(pk=DataSource.objects.create(name="UK VMD", slug="uk").pk).update(
        held_reason="File shrank by 40%"
    )
    monitoring.record(message="ReferenceError: x", url="/c")
    items = attention.report()["items"]
    sections = [(i["section"], i["severity"]) for i in items]
    assert ("automation", "danger") in sections
    assert ("sources", "warn") in sections
    assert ("errors", "warn") in sections
    assert any("UK VMD" in i["text"] for i in items)


def test_digest_pushes_to_staff_only_and_stays_quiet_when_nothing_is_wrong(monkeypatch):
    sent = []
    monkeypatch.setattr(
        "apps.push.service.notify", lambda user, title, body, path: sent.append(user.username) or 1
    )
    User.objects.create_user("admin", password="x", role=Role.ADMIN)
    User.objects.create_user("editor", password="x", role=Role.EDITOR)
    User.objects.create_user("visitor", password="x")

    all_ran_recently()
    out = attention.staff_digest()
    assert out["items"] == 0 and sent == []

    ran("feeds", hours_ago=0, status=RunStatus.FAILED, error="boom")
    out = attention.staff_digest()
    assert out["items"] >= 1
    assert sorted(sent) == ["admin", "editor"]


def test_digest_is_a_scheduled_task_and_the_staff_endpoint_needs_staff():
    assert "staff-digest" in TASKS
    client = APIClient()
    assert client.get("/api/v1/staff/attention/").status_code in (401, 403)
    client.force_authenticate(User.objects.create_user("ed", password="x", role=Role.EDITOR))
    body = client.get("/api/v1/staff/attention/").json()
    assert {"items", "missed_runs", "failed_runs", "price_outliers"} <= set(body)


def test_failed_images_wait_longer_after_each_attempt():
    ct = ContentType.objects.get_for_model(User)
    asset = ImageAsset.objects.create(
        content_type=ct,
        object_id=1,
        original_url="https://example.org/a.png",
        status=ImageStatus.FAILED,
        attempts=1,
        last_attempt_at=timezone.now(),
    )
    due = lambda: ImageAsset.objects.filter(images.retry_due(timezone.now())).exists()  # noqa: E731
    assert not due()  # just failed: wait a day
    ImageAsset.objects.filter(pk=asset.pk).update(
        last_attempt_at=timezone.now() - timedelta(days=1)
    )
    assert due()
    ImageAsset.objects.filter(pk=asset.pk).update(
        attempts=2, last_attempt_at=timezone.now() - timedelta(days=1)
    )
    assert not due()  # second failure waits two days
    ImageAsset.objects.filter(pk=asset.pk).update(
        last_attempt_at=timezone.now() - timedelta(days=2)
    )
    assert due()
    ImageAsset.objects.filter(pk=asset.pk).update(attempts=images.MAX_ATTEMPTS)
    assert not due()  # out of attempts: a person retries from the admin


def test_informational_items_alone_do_not_send_a_notification(monkeypatch):
    from apps.search.models import SearchMiss

    sent = []
    monkeypatch.setattr("apps.push.service.notify", lambda *a, **k: sent.append(1) or 1)
    User.objects.create_user("admin", password="x", role=Role.ADMIN)
    all_ran_recently()
    SearchMiss.objects.create(query="zzz", example="zzz", count=5)
    out = attention.staff_digest()
    assert out["items"] == 1 and sent == []
