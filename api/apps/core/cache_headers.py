"""Short shared-cache headers for the anonymous public catalogue (CDN / edge friendly).

Only an explicit allowlist of read-only catalogue endpoints is cacheable, and only for anonymous
requests (no session cookie) that succeeded without setting a cookie. Everything else, including
accounts, staff, exams and submissions, is left untouched.
"""

import re

from django.conf import settings

PUBLIC_READS = re.compile(
    r"^/api/v1/(?:"
    r"generics/(?:[\w-]+/)?|products/[\w-]+/(?:prices/|packs/)?|companies/[\w-]+/|"
    r"countries/(?:[\w-]+/)?|species/(?:[\w-]+/)?|drug-classes/(?:[\w-]+/)?|search/"
    r")$"
)
# Short on purpose: an unpublished record must disappear quickly.
CACHE_CONTROL = "public, s-maxage=60, stale-while-revalidate=60"


class PublicCatalogueCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.method == "GET"
            and response.status_code == 200
            and PUBLIC_READS.match(request.path)
            and settings.SESSION_COOKIE_NAME not in request.COOKIES
            and not response.cookies
            and "Cache-Control" not in response
        ):
            response["Cache-Control"] = CACHE_CONTROL
        return response
