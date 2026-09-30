"""Optional Sentry for server errors. Off unless SENTRY_DSN is set; never sends personal data."""

SENSITIVE_HEADERS = {"cookie", "authorization", "x-csrftoken", "x-web-proxy-secret", "x-client-ip"}


def scrub_event(event, hint=None):
    """Remove everything that could identify a person or carry a credential before sending."""
    request = event.get("request") or {}
    for key in ("cookies", "data", "query_string", "env"):
        request.pop(key, None)
    headers = request.get("headers")
    if isinstance(headers, dict):
        request["headers"] = {
            k: v for k, v in headers.items() if str(k).lower() not in SENSITIVE_HEADERS
        }
    event.pop("user", None)
    return event


def init(dsn: str, environment: str = "production", traces: float = 0.0) -> bool:
    """Start Sentry. Returns False (and does nothing) when no DSN is configured."""
    if not dsn:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        traces_sample_rate=traces,
        before_send=scrub_event,
        max_request_body_size="never",
    )
    return True
