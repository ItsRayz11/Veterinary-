"""Outbound HTTP for automation, hardened against SSRF and resource abuse.

Only public http(s) hosts on ports 80/443 are contacted. Every redirect target is re-validated,
responses are size-capped, and robots.txt is honoured. Every failure mode, including malformed
URLs and servers that do not speak HTTP, surfaces as `FetchError`, so one bad URL can never abort
a whole batch. Known limit: DNS is resolved for validation and again by the socket layer, so a
hostile DNS server could still rebind between the two; only staff-registered feeds and sources
are ever fetched, which keeps that risk low.
"""

import http.client
import ipaddress
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

USER_AGENT = "VetRefBot/1.0 (+contact via site; respects robots.txt)"
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_BYTES = 1_000_000
ALLOWED_PORTS = {80, 443}
CHUNK = 64 * 1024


class FetchError(Exception):
    """Any reason a fetch was refused or failed. The message is safe to store and show staff."""


def assert_public_url(url: str) -> None:
    try:
        parts = urlparse(url)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:  # e.g. port out of range, malformed IPv6 literal
        raise FetchError("The URL is not valid.") from exc
    if parts.scheme not in ("http", "https") or not hostname:
        raise FetchError("Only http and https URLs are allowed.")
    port = port or (443 if parts.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise FetchError("Only ports 80 and 443 are allowed.")
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError) as exc:
        raise FetchError("The host name could not be resolved.") from exc
    for info in infos:
        try:
            ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])  # drop an IPv6 zone id
        except ValueError as exc:
            raise FetchError("The host resolved to an unreadable address.") from exc
        if not ip.is_global:
            raise FetchError("The URL points to a non-public address.")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # redirects are followed manually so each hop is validated


_opener = urllib.request.build_opener(_NoRedirect)


def _remaining(deadline: float | None, timeout: float) -> float:
    """Socket timeout for the next step: never longer than what is left of the overall deadline."""
    if deadline is None:
        return timeout
    left = deadline - time.monotonic()
    if left <= 0:
        raise FetchError("Timed out.")
    return min(timeout, left)


def _read_limited(resp, max_bytes: int, deadline: float | None, timeout: float) -> bytes:
    body = bytearray()
    while len(body) <= max_bytes:
        _remaining(deadline, timeout)  # raises once the overall deadline has passed
        chunk = resp.read(min(CHUNK, max_bytes + 1 - len(body)))
        if not chunk:
            break
        body.extend(chunk)
    if len(body) > max_bytes:
        raise FetchError("The response is larger than the allowed size.")
    return bytes(body)


def fetch(
    url: str,
    *,
    method: str = "GET",
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = DEFAULT_TIMEOUT,
    deadline: float | None = None,
) -> tuple[int, bytes, str]:
    """Returns (status, body, final_url). HEAD returns an empty body.

    `timeout` bounds each network step; `deadline` (an absolute `time.monotonic()` value) bounds
    the whole call, redirects and body included.
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        assert_public_url(current)
        step = _remaining(deadline, timeout)
        try:
            req = urllib.request.Request(current, method=method, headers={"User-Agent": USER_AGENT})
            with _opener.open(req, timeout=step) as resp:
                body = (
                    b"" if method == "HEAD" else _read_limited(resp, max_bytes, deadline, timeout)
                )
                return resp.status, body, current
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location")
            if exc.code in (301, 302, 303, 307, 308) and location:
                current = urljoin(current, location)
                continue
            return exc.code, b"", current
        except FetchError:
            raise
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
            ValueError,
        ) as exc:
            reason = getattr(exc, "reason", None) or exc
            raise FetchError(f"Could not fetch: {type(exc).__name__}: {reason}"[:200]) from exc
    raise FetchError("Too many redirects.")


def allowed_by_robots(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    cache: dict | None = None,
    deadline: float | None = None,
) -> bool:
    """False when robots.txt disallows our agent, or when it cannot be determined for a 5xx.

    Pass the same `cache` dict for a batch of URLs so each host's robots.txt is fetched once.
    A cached value of None means "could not confirm permission" and denies the whole host.
    """
    try:
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
    except ValueError:
        return False
    if cache is not None and host in cache:
        parser = cache[host]
        return parser is not None and parser.can_fetch(USER_AGENT, url)
    parser = None
    try:
        status, body, _ = fetch(
            f"{host}/robots.txt", max_bytes=200_000, timeout=timeout, deadline=deadline
        )
        if not (status in (401, 403) or status >= 500):  # those mean permission is unconfirmed
            parser = RobotFileParser()
            parser.parse(
                body.decode("utf-8", errors="replace").splitlines() if status < 400 else []
            )
    except FetchError:
        parser = None
    if cache is not None:
        cache[host] = parser
    return parser is not None and parser.can_fetch(USER_AGENT, url)
