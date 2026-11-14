import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.companies.models import Company
from apps.core.models import ReviewStatus
from apps.countries.models import Country
from apps.pharma.models import Generic, GenericSynonym, Product
from apps.search.models import SearchMiss
from apps.search.services import core_query, search

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalogue():
    call_command("seed_reference")
    gb = Country.objects.get(iso2="GB")
    company = Company.objects.create(
        name="Example Pharma Ltd", country=gb, review_status=ReviewStatus.OFFICIAL_REGULATORY
    )
    generic = Generic.objects.create(
        name="Albendazole", review_status=ReviewStatus.OFFICIAL_REGULATORY
    )
    GenericSynonym.objects.create(generic=generic, synonym="Albendazol")
    for brand in ("Albex 10% Oral Suspension", "Valbazen"):
        Product.objects.create(
            brand_name=brand,
            generic=generic,
            manufacturer=company,
            review_status=ReviewStatus.OFFICIAL_REGULATORY,
        )
    return generic


def test_core_query_drops_form_strength_and_salt_words():
    assert core_query("albendazole 10 oral suspension") == "albendazole"
    assert core_query("enrofloxacin hcl") == "enrofloxacin"
    assert core_query("injection") == "injection"  # never reduced to nothing


def test_albendazole_found_by_generic_brand_spelling_and_form_words(catalogue):
    for q in ("albendazole", "ALBENDAZOLE", "Albendazol", "albendazole 10% oral suspension"):
        out = search(q)
        assert [g["name"] for g in out["generics"]] == ["Albendazole"], q
    brands = {p["name"] for p in search("albendazole")["products"]}
    assert {"Albex 10% Oral Suspension", "Valbazen"} <= brands  # brands of the matched generic
    assert [p["name"] for p in search("valbazen")["products"]] == ["Valbazen"]
    assert not SearchMiss.objects.exists()


def test_typo_gets_suggestions_and_fallback_and_is_logged(catalogue):
    out = search("albendazle")
    assert "Albendazole" in out["did_you_mean"] or out["generics"]
    miss = search("zzqxunknowndrug")
    assert miss["generics"] == [] and miss["fallback"]["popular_generics"][0]["slug"]
    assert miss["fallback"]["countries"]
    assert SearchMiss.objects.get(query="zzqxunknowndrug").count == 1
    search("ZZQX unknowndrug!")  # same text after normalising
    assert SearchMiss.objects.get(query="zzqx unknowndrug").count == 1
    search("zzqxunknowndrug")
    assert SearchMiss.objects.get(query="zzqxunknowndrug").count == 2


def test_misses_store_no_personal_data_and_ignore_junk(catalogue):
    for q in ("me@example.com", "https://x.test/a", "0912345678901", "a"):
        search(q)
    assert not SearchMiss.objects.exists()


def test_hidden_records_never_match(catalogue):
    Generic.objects.create(name="Secretdrug", review_status=ReviewStatus.IMPORTED_UNVERIFIED)
    out = search("secretdrug")
    assert out["generics"] == []
    assert SearchMiss.objects.filter(query="secretdrug").exists()


def test_search_api_logs_and_staff_report(catalogue):
    client = APIClient()
    assert client.get("/api/v1/search/", {"q": "nosuchmedicine"}).status_code == 200
    client.get("/api/v1/search/", {"q": "nosuchmedicine"})
    assert client.get("/api/v1/staff/search-misses/").status_code in (401, 403)
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    client.force_authenticate(editor)
    rows = client.get("/api/v1/staff/search-misses/").json()["results"]
    assert rows[0]["query"] == "nosuchmedicine" and rows[0]["count"] == 2
    done = client.post(f"/api/v1/staff/search-misses/{rows[0]['id']}/resolve/", {"resolved": True})
    assert done.json()["resolved"] is True
    assert client.get("/api/v1/staff/search-misses/").json()["results"] == []
