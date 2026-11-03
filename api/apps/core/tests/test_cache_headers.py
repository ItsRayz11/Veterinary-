import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_public_catalogue_is_cacheable_for_anonymous_only():
    api = APIClient()
    r = api.get("/api/v1/countries/")
    assert r.status_code == 200
    assert "s-maxage=60" in r["Cache-Control"]
    api.cookies["sessionid"] = "x"
    assert "s-maxage" not in api.get("/api/v1/countries/").get("Cache-Control", "")


def test_private_and_unlisted_endpoints_are_never_cached():
    api = APIClient()
    for path in ("/api/v1/auth/me/", "/api/v1/health/", "/api/v1/prices/submissions/"):
        assert "s-maxage" not in api.get(path).get("Cache-Control", ""), path
    assert "s-maxage" not in api.post("/api/v1/search/?q=aa").get("Cache-Control", "")
