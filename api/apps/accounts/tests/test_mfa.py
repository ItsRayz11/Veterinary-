"""Two-factor authentication: enrolment, sign-in, single use, recovery, enforcement."""

import itertools
import time

import pyotp
import pytest
from django.core.cache import cache
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts import mfa
from apps.accounts.models import RecoveryCode, Role, TotpDevice, User

PASSWORD = "Zq7!kLm29xWv"


@pytest.fixture(autouse=True)
def _clean(settings):
    cache.clear()
    settings.LOGIN_MAX_FAILURES = 1000  # only the MFA-specific lock test lowers this


def totp_now(secret, offset=0):
    return pyotp.TOTP(secret).at(time.time() + offset * 30)


def enrolled(username="rev", role=Role.VET_REVIEWER):
    """A user with two-factor fully on; returns (user, secret, recovery_codes)."""
    user = User.objects.create_user(username, password=PASSWORD, role=role)
    secret = mfa.begin_setup(user)["secret"]
    codes = mfa.confirm_setup(user, totp_now(secret))
    assert codes
    # The enrolment code counts as spent (see the replay test); most tests model a later day.
    TotpDevice.objects.filter(user=user).update(last_used_step=0)
    return User.objects.get(pk=user.pk), secret, codes


def logged_in_client(user, verified=False):
    c = APIClient()
    c.force_login(user)
    if verified:
        session = c.session
        session["mfa_verified"] = True
        session.save()
    return c


# ---------- enrolment ----------


def test_setup_then_confirm_turns_it_on_and_returns_recovery_codes(db):
    user = User.objects.create_user("u", password=PASSWORD)
    c = logged_in_client(user)
    setup = c.post("/api/v1/auth/mfa/setup/", {}, format="json").json()
    assert setup["secret"] and setup["otpauth_uri"].startswith("otpauth://totp/VetRef:u")
    assert mfa.enabled(User.objects.get(pk=user.pk)) is False  # not until a code is proven
    bad = c.post("/api/v1/auth/mfa/confirm/", {"code": "000000"}, format="json")
    assert bad.status_code == 400
    ok = c.post("/api/v1/auth/mfa/confirm/", {"code": totp_now(setup["secret"])}, format="json")
    body = ok.json()
    assert ok.status_code == 200 and body["enabled"] and len(body["recovery_codes"]) == 10
    assert all(len(code) == 11 and code[5] == "-" for code in body["recovery_codes"])
    assert c.get("/api/v1/auth/mfa/status/").json()["recovery_codes_left"] == 10


def test_cannot_set_up_twice_and_anonymous_cannot_touch_any_endpoint(db):
    user, _, _ = enrolled()
    c = logged_in_client(user)
    assert c.post("/api/v1/auth/mfa/setup/", {}, format="json").status_code == 400
    anon = APIClient()
    for url in ("setup", "confirm", "disable", "recovery", "status"):
        method = anon.get if url == "status" else anon.post
        assert method(f"/api/v1/auth/mfa/{url}/").status_code in (401, 403)


# ---------- secrets at rest ----------


def test_secret_is_encrypted_and_recovery_codes_are_hashed(db):
    user, secret, codes = enrolled()
    stored = TotpDevice.objects.get(user=user).secret
    assert secret not in stored and mfa._decrypt(stored) == secret
    hashes = set(RecoveryCode.objects.filter(user=user).values_list("code_hash", flat=True))
    assert len(hashes) == 10
    assert not any(code.replace("-", "") in h or code in h for h in hashes for code in codes)


def test_a_wrong_key_can_never_verify(db, settings):
    user, secret, _ = enrolled()
    settings.MFA_ENCRYPTION_KEY = (
        "eCfFqkxr3e0m0k3m4v0cQ1sZ8N3r9b4n1pXwYQw1T2I="  # a different valid key
    )
    assert mfa.verify(User.objects.get(pk=user.pk), totp_now(secret)) is False


# ---------- signing in ----------


def login_password(client, username="rev"):
    return client.post(
        "/api/v1/auth/login/", {"username": username, "password": PASSWORD}, format="json"
    )


def test_password_alone_does_not_sign_in_a_user_with_two_factor(db):
    enrolled()
    c = APIClient()
    r = login_password(c)
    assert r.status_code == 200 and r.json() == {"mfa_required": True}
    assert c.get("/api/v1/auth/me/").status_code in (401, 403)  # still anonymous


def test_code_completes_sign_in_and_marks_the_session_verified(db):
    _, secret, _ = enrolled()
    c = APIClient()
    login_password(c)
    wrong = c.post("/api/v1/auth/mfa/verify/", {"code": "123456"}, format="json")
    assert wrong.status_code == 400
    ok = c.post("/api/v1/auth/mfa/verify/", {"code": totp_now(secret)}, format="json")
    me = ok.json()
    assert ok.status_code == 200 and me["username"] == "rev" and me["mfa_verified"] is True
    assert c.get("/api/v1/auth/me/").status_code == 200


def test_verify_without_a_password_step_is_refused(db):
    _, secret, _ = enrolled()
    r = APIClient().post("/api/v1/auth/mfa/verify/", {"code": totp_now(secret)}, format="json")
    assert r.status_code == 400 and "expired" in str(r.json())


def test_a_code_works_once_even_inside_its_time_window(db):
    _, secret, _ = enrolled()
    code = totp_now(secret, offset=1)  # next step: valid, and not yet used by the enrolment
    a = APIClient()
    login_password(a)
    assert a.post("/api/v1/auth/mfa/verify/", {"code": code}, format="json").status_code == 200
    b = APIClient()
    login_password(b)
    assert b.post("/api/v1/auth/mfa/verify/", {"code": code}, format="json").status_code == 400


def test_clock_drift_window_accepts_one_step_each_way_but_not_two(db):
    user, secret, _ = enrolled()
    device = TotpDevice.objects.get(user=user)
    now = time.time()
    assert mfa._accepted_step(device, pyotp.TOTP(secret).at(now - 30), now) is not None
    assert mfa._accepted_step(device, pyotp.TOTP(secret).at(now + 30), now) is not None
    assert mfa._accepted_step(device, pyotp.TOTP(secret).at(now - 90), now) is None
    assert mfa._accepted_step(device, pyotp.TOTP(secret).at(now + 90), now) is None
    assert (
        mfa._accepted_step(device, "12345", now) is None
        and mfa._accepted_step(device, "abcdef", now) is None
    )


def test_a_half_finished_sign_in_expires(db):
    _, secret, _ = enrolled()
    c = APIClient()
    login_password(c)
    session = c.session
    session["mfa_pending_at"] = time.time() - mfa_views_pending() - 5
    session.save()
    r = c.post("/api/v1/auth/mfa/verify/", {"code": totp_now(secret, 1)}, format="json")
    assert r.status_code == 400 and "expired" in str(r.json())


def mfa_views_pending():
    from apps.accounts.mfa_views import PENDING_SECONDS

    return PENDING_SECONDS


def test_wrong_codes_lock_the_account_like_wrong_passwords(db, settings):
    _, secret, _ = enrolled()
    settings.LOGIN_MAX_FAILURES = 3
    c = APIClient()
    login_password(c)
    codes = [
        c.post("/api/v1/auth/mfa/verify/", {"code": "000000"}, format="json").status_code
        for _ in range(4)
    ]
    assert codes == [400, 400, 400, 429]
    locked = c.post("/api/v1/auth/mfa/verify/", {"code": totp_now(secret, 1)}, format="json")
    assert locked.status_code == 429  # even the right code waits out the lock


# ---------- recovery codes ----------


def test_recovery_code_signs_in_once_then_is_spent(db):
    _, _, codes = enrolled()
    first = APIClient()
    login_password(first)
    assert (
        first.post("/api/v1/auth/mfa/verify/", {"code": codes[0]}, format="json").status_code == 200
    )
    again = APIClient()
    login_password(again)
    assert (
        again.post("/api/v1/auth/mfa/verify/", {"code": codes[0]}, format="json").status_code == 400
    )
    assert first.get("/api/v1/auth/mfa/status/").json()["recovery_codes_left"] == 9


def test_regenerating_recovery_codes_invalidates_the_old_ones(db):
    user, secret, old = enrolled()
    c = logged_in_client(user, verified=True)
    r = c.post("/api/v1/auth/mfa/recovery/", {"code": totp_now(secret, 1)}, format="json")
    new = r.json()["recovery_codes"]
    assert r.status_code == 200 and len(new) == 10 and not set(new) & set(old)
    assert mfa.verify(User.objects.get(pk=user.pk), old[0]) is False
    assert mfa.verify(User.objects.get(pk=user.pk), new[0]) is True
    assert (
        c.post("/api/v1/auth/mfa/recovery/", {"code": "nonsense"}, format="json").status_code == 400
    )


# ---------- disabling ----------


def test_ordinary_users_can_turn_it_off_with_a_code(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    user, secret, _ = enrolled("plain", role=Role.REGISTERED)
    c = logged_in_client(user)
    assert c.post("/api/v1/auth/mfa/disable/", {"code": "000000"}, format="json").status_code == 400
    ok = c.post("/api/v1/auth/mfa/disable/", {"code": totp_now(secret, 1)}, format="json")
    assert ok.status_code == 200 and ok.json()["enabled"] is False
    assert not TotpDevice.objects.filter(user=user).exists()
    assert not RecoveryCode.objects.filter(user=user).exists()


def test_staff_cannot_turn_it_off_while_it_is_required(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    user, secret, _ = enrolled("boss", role=Role.ADMIN)
    c = logged_in_client(user, verified=True)
    r = c.post("/api/v1/auth/mfa/disable/", {"code": totp_now(secret, 1)}, format="json")
    assert r.status_code == 400 and "must keep" in str(r.json())
    assert TotpDevice.objects.filter(user=user).exists()


# ---------- enforcement on the staff API ----------


STAFF_URL = "/api/v1/staff/summary/"


def test_staff_api_refuses_a_session_that_has_not_passed_two_factor(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    for role in (Role.EDITOR, Role.REVIEWER, Role.VET_REVIEWER, Role.MODERATOR, Role.ADMIN):
        user = User.objects.create_user(f"s-{role}", password=PASSWORD, role=role)
        r = logged_in_client(user).get(STAFF_URL)
        assert r.status_code == 403 and r.json()["error"]["code"] == "mfa_required", role
        assert logged_in_client(user, verified=True).get(STAFF_URL).status_code == 200, role


def test_enforcement_can_be_switched_off_and_never_affects_ordinary_users(db, settings):
    staff = User.objects.create_user("st", password=PASSWORD, role=Role.EDITOR)
    settings.REQUIRE_STAFF_MFA = False
    assert logged_in_client(staff).get(STAFF_URL).status_code == 200
    settings.REQUIRE_STAFF_MFA = True
    student = User.objects.create_user("stu", password=PASSWORD, role=Role.STUDENT)
    assert logged_in_client(student).get(STAFF_URL).status_code == 403  # role, not MFA
    assert logged_in_client(student).get("/api/v1/auth/me/").status_code == 200


def test_me_reports_what_the_web_app_needs(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    staff = User.objects.create_user("st", password=PASSWORD, role=Role.MODERATOR)
    me = logged_in_client(staff).get("/api/v1/auth/me/").json()
    assert (me["mfa_enabled"], me["mfa_required"], me["mfa_verified"]) == (False, True, False)
    me = logged_in_client(staff, verified=True).get("/api/v1/auth/me/").json()
    assert me["mfa_verified"] is True


# ---------- the Django admin ----------


_admins = itertools.count(1)


def admin_client(verified=False):
    user = User.objects.create_superuser(
        f"root{next(_admins)}", password=PASSWORD, email="r@example.org"
    )
    c = Client()
    c.force_login(user)
    if verified:
        session = c.session
        session["mfa_verified"] = True
        session.save()
    return c, user


def test_admin_redirects_unverified_staff_to_the_two_factor_page(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    c, _ = admin_client()
    r = c.get("/admin/")
    assert r.status_code == 302 and r["Location"].startswith(
        "/api/v1/auth/mfa/admin/?next=%2Fadmin%2F"
    )
    assert admin_client(verified=True)[0].get("/admin/").status_code == 200


def test_admin_is_untouched_when_two_factor_is_not_required(db, settings):
    settings.REQUIRE_STAFF_MFA = False
    assert admin_client()[0].get("/admin/").status_code == 200


def test_admin_login_and_logout_pages_stay_reachable(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    c, _ = admin_client()
    assert c.get("/admin/login/").status_code in (200, 302)
    assert (
        c.get("/admin/login/").get("Location", "")
        != "/api/v1/auth/mfa/admin/?next=%2Fadmin%2Flogin%2F"
    )
    assert c.post("/admin/logout/").status_code in (200, 302)


def test_admin_page_walks_through_enrolment_then_verification(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    c, user = admin_client()
    page = c.get("/api/v1/auth/mfa/admin/?next=/admin/")
    html = page.content.decode()
    assert page.status_code == 200 and "Turn on two-factor" in html
    secret = mfa._decrypt(TotpDevice.objects.get(user=user).secret)
    assert secret in html
    wrong = c.post("/api/v1/auth/mfa/admin/", {"code": "000000", "next": "/admin/"})
    assert "not right" in wrong.content.decode()
    done = c.post("/api/v1/auth/mfa/admin/", {"code": totp_now(secret), "next": "/admin/"})
    assert "recovery codes" in done.content.decode() and mfa.enabled(User.objects.get(pk=user.pk))
    assert c.get("/admin/").status_code == 200  # this session is now verified
    # a new session must verify with a code
    c2 = Client()
    c2.force_login(user)
    assert "Verify" in c2.get("/api/v1/auth/mfa/admin/").content.decode()
    assert c2.get("/admin/").status_code == 302
    ok = c2.post("/api/v1/auth/mfa/admin/", {"code": totp_now(secret, 1), "next": "/admin/"})
    assert ok.status_code == 302 and ok["Location"] == "/admin/"
    assert c2.get("/admin/").status_code == 200


def test_admin_page_never_redirects_to_another_site(db, settings):
    settings.REQUIRE_STAFF_MFA = True
    user, secret, codes = enrolled("adm", role=Role.ADMIN)
    c = Client()
    c.force_login(user)
    r = c.post(
        "/api/v1/auth/mfa/admin/",
        {"code": totp_now(secret, 1), "next": "https://evil.example/x"},
    )
    assert r.status_code == 302 and r["Location"] == "/"
    c2 = Client()
    c2.force_login(user)
    r = c2.post("/api/v1/auth/mfa/admin/", {"code": codes[0], "next": "//evil.example"})
    assert r.status_code == 302 and r["Location"] == "/"


def test_admin_page_requires_a_session(db):
    r = Client().get("/api/v1/auth/mfa/admin/")
    assert r.status_code == 302 and r["Location"].startswith("/admin/login/")


def test_the_code_used_to_enrol_cannot_be_replayed_to_sign_in(db):
    user = User.objects.create_user("replay", password=PASSWORD, role=Role.VET_REVIEWER)
    secret = mfa.begin_setup(user)["secret"]
    code = totp_now(secret)
    assert mfa.confirm_setup(user, code)
    c = APIClient()
    login_password(c, "replay")
    assert c.post("/api/v1/auth/mfa/verify/", {"code": code}, format="json").status_code == 400
