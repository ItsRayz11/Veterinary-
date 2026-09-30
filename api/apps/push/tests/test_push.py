"""Web push: subscription safety, delivery, pruning and the listing-decision trigger."""

import pytest
from django.core.cache import cache
from pywebpush import WebPushException
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.push import service
from apps.push.models import PushSubscription

GOOD = "https://fcm.googleapis.com/fcm/send/abc123"
SUB = {"endpoint": GOOD, "keys": {"p256dh": "BPkey", "auth": "authsecret"}}


@pytest.fixture(autouse=True)
def _vapid(settings):
    cache.clear()
    settings.VAPID_PUBLIC_KEY = "public"
    settings.VAPID_PRIVATE_KEY = "private"


@pytest.fixture
def user(db):
    return User.objects.create_user("pusher", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_login(user)
    return c


class _Resp:
    def __init__(self, code):
        self.status_code = code


def test_config_is_public_and_hides_key_when_disabled(db, settings):
    anon = APIClient()
    assert anon.get("/api/v1/push/config/").json() == {"enabled": True, "public_key": "public"}
    settings.VAPID_PRIVATE_KEY = ""
    assert anon.get("/api/v1/push/config/").json() == {"enabled": False, "public_key": ""}


def test_subscribe_requires_login(db):
    assert APIClient().post("/api/v1/push/subscribe/", SUB, format="json").status_code in (401, 403)


def test_subscribe_stores_and_is_idempotent(api, user):
    assert api.post("/api/v1/push/subscribe/", SUB, format="json").status_code == 201
    assert api.post("/api/v1/push/subscribe/", SUB, format="json").status_code == 201
    assert PushSubscription.objects.filter(user=user).count() == 1


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/x",  # not https
        "https://169.254.169.254/latest/meta-data",  # internal address
        "https://localhost/x",
        "https://evil.example.com/fcm.googleapis.com",
        "https://fcm.googleapis.com.evil.com/x",  # look-alike host
        "https://user:pw@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:8443/x",
        "https://fcm.googleapis.com:notaport/x",
        "",
    ],
)
def test_endpoint_must_be_a_known_push_service(api, endpoint):
    body = {"endpoint": endpoint, "keys": SUB["keys"]}
    assert api.post("/api/v1/push/subscribe/", body, format="json").status_code == 400
    assert PushSubscription.objects.count() == 0


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"endpoint": GOOD},
        {"endpoint": GOOD, "keys": "nope"},
        {"endpoint": GOOD, "keys": {"p256dh": 1, "auth": 2}},
        {"endpoint": ["x"], "keys": SUB["keys"]},
        {"endpoint": GOOD, "keys": {"p256dh": "k" * 500, "auth": "a"}},
    ],
)
def test_malformed_subscriptions_are_rejected_not_crashed(api, body):
    assert api.post("/api/v1/push/subscribe/", body, format="json").status_code == 400


def test_disabled_server_does_not_accept_subscriptions(api, settings):
    settings.VAPID_PRIVATE_KEY = ""
    assert api.post("/api/v1/push/subscribe/", SUB, format="json").status_code == 404


def test_a_user_keeps_only_the_newest_devices(user):
    for i in range(service.MAX_PER_USER + 3):
        assert service.subscribe(user, f"https://fcm.googleapis.com/fcm/send/{i}", "k", "a")
    assert PushSubscription.objects.filter(user=user).count() == service.MAX_PER_USER


def test_unsubscribe_only_removes_own_device(api, user):
    other = User.objects.create_user("other", password="x")
    service.subscribe(other, "https://fcm.googleapis.com/fcm/send/theirs", "k", "a")
    api.post("/api/v1/push/subscribe/", SUB, format="json")
    api.post("/api/v1/push/unsubscribe/", {"endpoint": GOOD}, format="json")
    api.post(
        "/api/v1/push/unsubscribe/",
        {"endpoint": "https://fcm.googleapis.com/fcm/send/theirs"},
        format="json",
    )
    assert not PushSubscription.objects.filter(user=user).exists()
    assert PushSubscription.objects.filter(user=other).count() == 1


def test_notify_sends_payload_to_each_device(user, monkeypatch):
    service.subscribe(user, GOOD, "k", "a")
    service.subscribe(user, GOOD + "2", "k", "a")
    sent = []
    monkeypatch.setattr(service, "_send_one", lambda sub, payload: sent.append(payload))
    assert service.notify(user, "Hello", "Body", "/jobs/1") == 2
    assert '"url": "/jobs/1"' in sent[0]


def test_notify_refuses_offsite_paths(user, monkeypatch):
    service.subscribe(user, GOOD, "k", "a")
    monkeypatch.setattr(service, "_send_one", lambda *a: pytest.fail("must not send"))
    assert service.notify(user, "t", "b", "https://evil.example") == 0
    assert service.notify(user, "t", "b", "//evil.example") == 0


def test_expired_subscriptions_are_removed_but_other_errors_keep_them(user, monkeypatch):
    service.subscribe(user, GOOD, "k", "a")
    service.subscribe(user, GOOD + "2", "k", "a")

    def fake(sub, payload):
        code = 410 if sub.endpoint == GOOD else 500
        raise WebPushException("x", response=_Resp(code))

    monkeypatch.setattr(service, "_send_one", fake)
    assert service.notify(user, "t", "b") == 0
    assert list(PushSubscription.objects.values_list("endpoint", flat=True)) == [GOOD + "2"]


def test_network_failure_never_raises(user, monkeypatch):
    service.subscribe(user, GOOD, "k", "a")

    def boom(*a):
        raise ConnectionError("down")

    monkeypatch.setattr(service, "_send_one", boom)
    assert service.notify(user, "t", "b") == 0


def test_nothing_is_sent_when_disabled(user, settings, monkeypatch):
    service.subscribe(user, GOOD, "k", "a")
    settings.VAPID_PRIVATE_KEY = ""
    monkeypatch.setattr(service, "_send_one", lambda *a: pytest.fail("must not send"))
    assert service.notify(user, "t", "b") == 0


def test_listing_decision_notifies_the_poster(db, monkeypatch, django_capture_on_commit_callbacks):
    from apps.opportunities import services as listings
    from apps.opportunities.models import Job

    poster = User.objects.create_user("poster", password="x")
    mod = User.objects.create_user("mod", password="x", role=Role.MODERATOR)
    job = Job.objects.create(
        title="Vet",
        organization="Clinic",
        description="d",
        apply_url="https://example.com/apply",
        submitted_by=poster,
    )
    calls = []
    monkeypatch.setattr(service, "notify", lambda *a: calls.append(a))
    with django_capture_on_commit_callbacks(execute=True):
        listings.approve(job, mod)
    assert len(calls) == 1
    assert calls[0][0] == poster and calls[0][3] == f"/jobs/{job.pk}"
