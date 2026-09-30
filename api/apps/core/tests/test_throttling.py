"""Per-IP throttling must not be steerable by client-supplied headers."""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.core.throttling import client_ip

SECRET = "proxy-secret-for-tests"


class FakeRequest:
    def __init__(self, **meta):
        self.META = meta


def test_without_a_secret_configured_forwarding_headers_are_ignored(settings):
    settings.WEB_PROXY_SECRET = ""
    r = FakeRequest(
        REMOTE_ADDR="10.0.0.9",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
        HTTP_X_CLIENT_IP="1.2.3.4",
        HTTP_X_WEB_PROXY_SECRET="anything",
    )
    assert client_ip(r) == "10.0.0.9"


def test_matching_secret_makes_x_client_ip_trusted(settings):
    settings.WEB_PROXY_SECRET = SECRET
    r = FakeRequest(
        REMOTE_ADDR="10.0.0.9", HTTP_X_CLIENT_IP="203.0.113.7", HTTP_X_WEB_PROXY_SECRET=SECRET
    )
    assert client_ip(r) == "203.0.113.7"
    v6 = FakeRequest(
        REMOTE_ADDR="10.0.0.9", HTTP_X_CLIENT_IP="2001:db8::1", HTTP_X_WEB_PROXY_SECRET=SECRET
    )
    assert client_ip(v6) == "2001:db8::1"


@pytest.mark.parametrize(
    "meta",
    [
        {"HTTP_X_CLIENT_IP": "203.0.113.7", "HTTP_X_WEB_PROXY_SECRET": "wrong"},
        {"HTTP_X_CLIENT_IP": "203.0.113.7"},  # secret header missing
        {"HTTP_X_CLIENT_IP": "not-an-ip", "HTTP_X_WEB_PROXY_SECRET": SECRET},  # malformed
        {"HTTP_X_CLIENT_IP": "", "HTTP_X_WEB_PROXY_SECRET": SECRET},
        {"HTTP_X_FORWARDED_FOR": "203.0.113.7"},  # spoofed forwarding header alone
    ],
)
def test_untrusted_or_malformed_headers_fall_back_to_the_socket_address(settings, meta):
    settings.WEB_PROXY_SECRET = SECRET
    assert client_ip(FakeRequest(REMOTE_ADDR="10.0.0.9", **meta)) == "10.0.0.9"


def login(client, username, **headers):
    return client.post(
        "/api/v1/auth/login/", {"username": username, "password": "x"}, format="json", **headers
    )


@pytest.fixture(autouse=True)
def _fresh_cache(settings):
    cache.clear()
    settings.LOGIN_MAX_FAILURES = (
        10_000  # these tests are about the per-IP limit, not account locks
    )


def test_spoofing_x_forwarded_for_does_not_escape_the_login_limit(db, settings):
    settings.WEB_PROXY_SECRET = SECRET
    api = APIClient()
    codes = [
        login(
            api, "nobody", HTTP_X_FORWARDED_FOR=f"9.9.9.{i}", HTTP_X_CLIENT_IP=f"8.8.8.{i}"
        ).status_code
        for i in range(14)
    ]
    assert 429 in codes  # rotating the headers did not buy a fresh bucket (limit is 10/min)


def test_a_trusted_proxy_gives_each_real_client_its_own_bucket(db, settings):
    settings.WEB_PROXY_SECRET = SECRET
    api = APIClient()

    def as_client(ip):
        return login(api, "nobody", HTTP_X_CLIENT_IP=ip, HTTP_X_WEB_PROXY_SECRET=SECRET).status_code

    assert [as_client("198.51.100.1") for _ in range(11)][-1] == 429  # client A is limited
    assert as_client("198.51.100.2") == 400  # client B is unaffected (bad credentials, not 429)
