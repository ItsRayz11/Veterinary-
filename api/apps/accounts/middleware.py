"""Keep the Django admin behind two-factor authentication for staff."""

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.http import urlencode

from . import mfa


class StaffMFAMiddleware:
    """When two-factor is required, a staff session may only use the admin after passing it.

    The admin has its own password form, so a session can exist without the second factor;
    this sends it to a small server-rendered page to enrol or verify first.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefix = "/" + settings.ADMIN_URL
        user = getattr(request, "user", None)
        if (
            request.path.startswith(prefix)
            and not request.path.endswith(("logout/", "login/"))
            and mfa.required_for(user)
            and not mfa.session_passed(request)
        ):
            return HttpResponseRedirect(
                "/api/v1/auth/mfa/admin/?" + urlencode({"next": request.get_full_path()})
            )
        return self.get_response(request)
