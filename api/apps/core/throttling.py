"""Client identity for per-IP throttling.

Behind proxies the connection address is the proxy's, and `X-Forwarded-For` is client-controlled
unless a trusted hop overwrites it, so neither can be trusted blindly. The web app's proxy
(`web/src/proxy.ts`) forwards the real client IP in `X-Client-IP` together with a shared secret
in `X-Web-Proxy-Secret`. The API believes `X-Client-IP` only when that secret matches
(`WEB_PROXY_SECRET`); otherwise it uses the socket address and ignores every forwarding header,
so nobody can pick their own throttle bucket by spoofing headers.
"""

import hmac
import ipaddress

from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


def client_ip(request) -> str:
    secret = getattr(settings, "WEB_PROXY_SECRET", "")
    supplied = request.META.get("HTTP_X_WEB_PROXY_SECRET", "")
    if secret and supplied and hmac.compare_digest(supplied.encode(), secret.encode()):
        try:
            return str(ipaddress.ip_address(request.META.get("HTTP_X_CLIENT_IP", "").strip()))
        except ValueError:
            pass  # a trusted proxy that sent a malformed address: fall back to the socket
    return request.META.get("REMOTE_ADDR", "")


class ClientIPMixin:
    def get_ident(self, request):
        return client_ip(request)


class AnonThrottle(ClientIPMixin, AnonRateThrottle):
    pass


class UserThrottle(ClientIPMixin, UserRateThrottle):
    pass
