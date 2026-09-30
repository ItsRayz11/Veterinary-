"""Per-account lockout: many attempts, from any addresses, cannot grind down one password."""

import itertools

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import AuditLog

GOOD = "Zq7!kLm29xWv"


_ips = itertools.count(1)


@pytest.fixture(autouse=True)
def _clean(settings):
    cache.clear()
    settings.LOGIN_MAX_FAILURES = 4
    settings.LOGIN_LOCK_SECONDS = 600


def attempt(client, username, password, ip=None):
    """Each call comes from a fresh address so the per-IP throttle never interferes."""
    if ip is None:
        n = next(_ips)
        ip = f"203.0.{n // 250}.{n % 250 + 1}"
    return client.post(
        "/api/v1/auth/login/",
        {"username": username, "password": password},
        format="json",
        REMOTE_ADDR=ip,
    )


def test_account_locks_after_repeated_failures_even_from_different_addresses(db):
    User.objects.create_user("victim", password=GOOD)
    api = APIClient()
    codes = [
        attempt(api, "victim", f"wrong-{i}", ip=f"198.51.100.{i}").status_code for i in range(6)
    ]
    assert codes[:3] == [400, 400, 400] and codes[3] == 400  # the 4th failure triggers the lock
    assert codes[4] == 429 and codes[5] == 429
    # even the correct password is refused while locked
    locked = attempt(api, "victim", GOOD, ip="192.0.2.77")
    assert locked.status_code == 429 and "Try again" in locked.json()["error"]["message"]
    assert AuditLog.objects.filter(action="login_locked").count() == 1


def test_lock_looks_identical_for_unknown_usernames(db):
    """No user enumeration: a made-up name locks exactly like a real one."""
    api = APIClient()
    codes = [attempt(api, "nobody-here", "x").status_code for _ in range(6)]
    assert codes == [400, 400, 400, 400, 429, 429]
    message = attempt(api, "nobody-here", "x").json()["error"]["message"]
    User.objects.create_user("real", password=GOOD)
    for _ in range(4):
        attempt(api, "real", "bad")
    assert attempt(api, "real", "bad").json()["error"]["message"] == message


def test_success_resets_the_counter(db):
    User.objects.create_user("carol", password=GOOD)
    api = APIClient()
    for _ in range(3):
        assert attempt(api, "carol", "bad").status_code == 400
    assert attempt(api, "carol", GOOD).status_code == 200  # counter cleared
    api.post("/api/v1/auth/logout/", format="json")
    for _ in range(3):
        assert attempt(APIClient(), "carol", "bad").status_code == 400
    assert attempt(APIClient(), "carol", GOOD).status_code == 200  # never reached 4 in a row


def test_username_matching_ignores_case_and_spacing(db):
    api = APIClient()
    for name in ("Dave", "dave", " DAVE ", "dAvE"):
        attempt(api, name, "bad")
    assert attempt(api, "dave", "bad").status_code == 429


def test_lock_expires(db, settings):
    User.objects.create_user("erin", password=GOOD)
    api = APIClient()
    for _ in range(4):
        attempt(api, "erin", "bad")
    assert attempt(api, "erin", GOOD).status_code == 429
    cache.clear()  # what expiry does to the lock entry
    assert attempt(api, "erin", GOOD).status_code == 200


def test_other_accounts_are_unaffected(db):
    User.objects.create_user("frank", password=GOOD)
    api = APIClient()
    for _ in range(5):
        attempt(api, "mallory-target", "bad")
    assert attempt(api, "frank", GOOD).status_code == 200
