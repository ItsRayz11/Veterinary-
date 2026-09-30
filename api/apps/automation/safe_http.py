"""Outbound HTTP for automation, hardened against SSRF and resource abuse.

Only public http(s) hosts on ports 80/443 are contacted. Every redirect target is re-validated,
responses are size-capped, and robots.txt is honoured. Known limit: DNS is resolved for validation
and again by the socket layer, so a hostile DNS server could still rebind between the two; only
staff-registered feeds and sources are ever fetched, which keeps that risk low.
"""

import ipaddress
import socket
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

USER_AGENT = "VetRefBot/1.0 (+contact via site; respects robots.txt)"
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_BYTES = 1_000_000
ALLOWED_PORTS = {80, 443}


class FetchError(Exception):
    """Any reason a fetch was refused or failed. The message is safe to store and show staff."""


def assert_public_url(url: str) -> None:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http and https URLs are allowed.")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise FetchError("Only ports 80 and 443 are allowed.")
    try:
        infos = socket.getaddrinfo(parts.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError("The host name could not be resolved.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError("The URL points to a non-public address.")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # redirects are followed manually so each hop is validated


_opener = urllib.request.build_opener(_NoRedirect)


def fetch(
    url: str,
    *,
    method: str = "GET",
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, bytes, str]:
    """Returns (status, body, final_url). HEAD returns an empty body."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        assert_public_url(current)
        req = urllib.request.Request(current, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with _opener.open(req, timeout=timeout) as resp:
                body = b"" if method == "HEAD" else resp.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise FetchError("The response is larger than the allowed size.")
                return resp.status, body, current
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location")
            if exc.code in (301, 302, 303, 307, 308) and location:
                current = urljoin(current, location)
                continue
            return exc.code, b"", current
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise FetchError(f"Could not connect: {getattr(exc, 'reason', exc)}"[:200]) from exc
    raise FetchError("Too many redirects.")


def allowed_by_robots(url: str) -> bool:
    """False when robots.txt disallows our agent, or when it cannot be determined for a 5xx."""
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        status, body, _ = fetch(robots_url, max_bytes=200_000)
    except FetchError:
        return False
    if status in (401, 403) or status >= 500:
        return False  # cannot confirm permission
    parser = RobotFileParser()
    parser.parse(body.decode("utf-8", errors="replace").splitlines() if status < 400 else [])
    return parser.can_fetch(USER_AGENT, url)
