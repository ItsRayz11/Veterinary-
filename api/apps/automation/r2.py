"""Minimal Cloudflare R2 client (S3-compatible, AWS Signature V4) using only the standard library,
so no extra dependency ships to the serverless runtime.

Credentials come from server settings only (`R2_*`). Nothing in this module returns or logs a
secret, and the signed request never leaves the server. `transport` is injectable so the signing
and failure handling are tested without the network.
"""

import hashlib
import hmac
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

from django.conf import settings

Transport = Callable[[str, str, dict, bytes], tuple[int, bytes]]

REGION = "auto"
SERVICE = "s3"


class R2Error(Exception):
    """A storage failure with a message that is safe to store and show to staff."""


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    endpoint: str = ""
    public_base_url: str = ""

    @classmethod
    def from_settings(cls) -> "R2Config | None":
        c = cls(
            settings.R2_ACCOUNT_ID,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY,
            settings.R2_BUCKET,
            settings.R2_ENDPOINT,
            settings.R2_PUBLIC_BASE_URL.rstrip("/"),
        )
        ok = c.access_key_id and c.secret_access_key and c.bucket and (c.account_id or c.endpoint)
        return c if ok else None

    @property
    def host(self) -> str:
        if self.endpoint:
            return self.endpoint.removeprefix("https://").rstrip("/")
        return f"{self.account_id}.r2.cloudflarestorage.com"

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{quote(key, safe='/-_.~')}" if self.public_base_url else ""


def configured() -> bool:
    return R2Config.from_settings() is not None


def public_url_for(key: str) -> str:
    cfg = R2Config.from_settings()
    return cfg.public_url(key) if cfg and key else ""


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sign_headers(
    *,
    method: str,
    host: str,
    path: str,
    headers: dict[str, str],
    payload_sha256: str,
    access_key: str,
    secret_key: str,
    amz_date: str,
    region: str = REGION,
    service: str = SERVICE,
    query: str = "",
) -> dict[str, str]:
    """AWS Signature V4. Returns `headers` plus x-amz-date, x-amz-content-sha256 and Authorization.
    `path` must already be URI-encoded."""
    date = amz_date[:8]
    all_headers = {
        **{k.lower(): " ".join(str(v).split()) for k, v in headers.items()},
        "host": host,
        "x-amz-content-sha256": payload_sha256,
        "x-amz-date": amz_date,
    }
    names = sorted(all_headers)
    canonical = "\n".join(
        [
            method,
            path,
            query,
            "".join(f"{n}:{all_headers[n]}\n" for n in names),
            ";".join(names),
            payload_sha256,
        ]
    )
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )
    k = _hmac(("AWS4" + secret_key).encode(), date)
    for part in (region, service, "aws4_request"):
        k = _hmac(k, part)
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={';'.join(names)}, Signature={signature}"
    )
    out = {k_: v for k_, v in all_headers.items() if k_ != "host"}
    out["Authorization"] = auth
    return out


def _urllib_transport(method: str, url: str, headers: dict, body: bytes) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body or None, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed https R2 host
            return resp.status, resp.read(2000)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(2000)


def _request(
    cfg: R2Config, method: str, key: str, body: bytes, extra: dict, transport: Transport | None
) -> tuple[int, bytes]:
    path = "/" + quote(f"{cfg.bucket}/{key}", safe="/-_.~")
    headers = sign_headers(
        method=method,
        host=cfg.host,
        path=path,
        headers=extra,
        payload_sha256=hashlib.sha256(body).hexdigest(),
        access_key=cfg.access_key_id,
        secret_key=cfg.secret_access_key,
        amz_date=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
    )
    try:
        return (transport or _urllib_transport)(method, f"https://{cfg.host}{path}", headers, body)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise R2Error(f"R2 unreachable: {type(exc).__name__}") from exc


def _meta(metadata: dict[str, str]) -> dict[str, str]:
    """S3 user metadata travels as HTTP headers, so values must be ASCII: percent-encode them."""
    return {f"x-amz-meta-{k}": quote(str(v), safe="")[:1000] for k, v in metadata.items() if v}


def put_object(
    key: str,
    body: bytes,
    content_type: str,
    metadata: dict[str, str] | None = None,
    *,
    transport: Transport | None = None,
) -> None:
    cfg = R2Config.from_settings()
    if cfg is None:
        raise R2Error("Cloudflare R2 is not configured on the server.")
    extra = {
        "content-type": content_type,
        "cache-control": "public, max-age=31536000, immutable",
        **_meta(metadata or {}),
    }
    status, _ = _request(cfg, "PUT", key, body, extra, transport)
    if status not in (200, 201):
        raise R2Error(f"R2 refused the upload (HTTP {status}).")


def object_exists(key: str, *, transport: Transport | None = None) -> bool:
    cfg = R2Config.from_settings()
    if cfg is None:
        raise R2Error("Cloudflare R2 is not configured on the server.")
    status, _ = _request(cfg, "HEAD", key, b"", {}, transport)
    if status == 404:
        return False
    if status == 200:
        return True
    raise R2Error(f"R2 check failed (HTTP {status}).")
