"""URL normalisation for the source registry. Pure functions, safe to import from migrations."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = ("utm_", "fbclid", "gclid", "mc_", "ref_src")


def canonicalize_url(url: str) -> str:
    """Stable identity for a web page: https, lower-case host without `www.`/mobile prefixes,
    no fragment, tracking parameters or default port, no trailing slash.
    '' if it is not an http(s) URL."""
    try:
        parts = urlsplit((url or "").strip())
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return ""
    if parts.scheme.lower() not in ("http", "https") or not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    # en.m.wikipedia.org -> en.wikipedia.org
    labels = host.split(".")
    labels = [x for i, x in enumerate(labels) if not (i < len(labels) - 2 and x in ("m", "mobile"))]
    host = ".".join(labels)
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    path = parts.path.rstrip("/")
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(_TRACKING))
    )
    return urlunsplit(("https", netloc, path, query, ""))[:1000]


def host_of(url: str) -> str:
    try:
        return (urlsplit(url or "").hostname or "").lower()
    except ValueError:
        return ""
