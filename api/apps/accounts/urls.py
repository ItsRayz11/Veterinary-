from django.urls import path

from . import mfa_views, views

urlpatterns = [
    path("auth/csrf/", views.csrf),
    path("auth/register/", views.register),
    path("auth/login/", views.login_view),
    path("auth/logout/", views.logout_view),
    path("auth/me/", views.me),
    path("auth/mfa/status/", mfa_views.mfa_status),
    path("auth/mfa/setup/", mfa_views.mfa_setup),
    path("auth/mfa/confirm/", mfa_views.mfa_confirm),
    path("auth/mfa/verify/", mfa_views.mfa_verify),
    path("auth/mfa/disable/", mfa_views.mfa_disable),
    path("auth/mfa/recovery/", mfa_views.mfa_recovery),
    path("auth/mfa/admin/", mfa_views.mfa_admin_page),
]
