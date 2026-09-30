from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.clinical.models import DoseRegimen, Route
from apps.core import review
from apps.core.models import ReviewStatus
from apps.pharma.models import Generic
from apps.sources.models import Source, SourceLink
from apps.species.models import Species
from apps.units.models import Unit


@pytest.fixture
def api(db):
    call_command("seed_dev_catalog")
    return APIClient()


def test_generic_detail_lists_all_brands_with_manufacturers(api):
    r = api.get("/api/v1/generics/enrofloxacin/")
    assert r.status_code == 200
    data = r.json()
    assert len(data["brands"]) == 2
    assert data["status"]["is_development_data"] is True
    assert data["doses"] == [] and "disclaimer" in data


def test_hidden_when_dev_flag_off(api, settings):
    settings.SHOW_DEVELOPMENT_DATA = False
    assert api.get("/api/v1/generics/enrofloxacin/").status_code == 404
    assert api.get("/api/v1/search/?q=enro").json()["generics"] == []


def test_product_and_company_pages_link_back(api):
    brands = api.get("/api/v1/generics/enrofloxacin/").json()["brands"]
    product = api.get(f"/api/v1/products/{brands[0]['slug']}/").json()
    assert product["ingredients"][0]["name"] == "Enrofloxacin"
    assert product["registrations"][0]["country"] == "PK"
    company = api.get(f"/api/v1/companies/{product['manufacturer']['slug']}/").json()
    assert [p["slug"] for p in company["products"]] == [product["slug"]]


def test_country_filter_on_generic(api):
    assert len(api.get("/api/v1/generics/enrofloxacin/?country=PK").json()["brands"]) == 2
    assert api.get("/api/v1/generics/enrofloxacin/?country=IN").json()["brands"] == []


def test_search_grouped_and_typo_tolerant(api):
    r = api.get("/api/v1/search/?q=enrofloxacin").json()
    assert r["generics"][0]["slug"] == "enrofloxacin"
    assert {p["name"] for p in r["products"]} == set()  # brands are DEV-Enro N, not matching
    assert api.get("/api/v1/search/?q=DEV-Enro").json()["products"]
    typo = api.get("/api/v1/search/?q=enrofloxacine").json()
    assert typo["did_you_mean"] == ["Enrofloxacin"]
    assert api.get("/api/v1/search/?q=e").json()["generics"] == []


def test_dose_shown_with_sources_and_only_verified_is_calculator_ready(api):
    generic = Generic.objects.get(slug="enrofloxacin")
    generic.is_development_data = False
    generic.review_status = ReviewStatus.MANUFACTURER_SUPPLIED
    generic.save()
    dose = DoseRegimen.objects.create(
        generic=generic,
        species=Species.objects.get(slug="cattle"),
        route=Route.objects.create(code="SC", name="Subcutaneous"),
        dose_unit=Unit.objects.get(code="mg/kg"),
        dose_min=Decimal("2.5"),
        dose_max=Decimal("5"),
        is_development_data=False,
    )
    src = Source.objects.create(source_type="other", title="Ref", url="https://example.org")
    SourceLink.objects.create(
        source=src, content_type=ContentType.objects.get_for_model(dose), object_id=dose.pk
    )
    # not public until reviewed
    assert api.get("/api/v1/generics/enrofloxacin/").json()["doses"] == []
    editor = User.objects.create_user("e", password="x", role=Role.EDITOR)
    review.set_review_status(dose, ReviewStatus.MANUFACTURER_SUPPLIED, editor)
    d = api.get("/api/v1/generics/enrofloxacin/").json()["doses"][0]
    assert d["calculator_ready"] is False and d["sources"][0]["title"] == "Ref"
    vet = User.objects.create_user("v", password="x", role=Role.VET_REVIEWER)
    review.set_review_status(dose, ReviewStatus.VERIFIED, vet)
    assert api.get("/api/v1/generics/enrofloxacin/").json()["doses"][0]["calculator_ready"] is True
    assert len(api.get("/api/v1/generics/enrofloxacin/?species=dog").json()["doses"]) == 0


def test_calculator_endpoint(api):
    ok = api.post(
        "/api/v1/calculators/dose_calc/",
        {"weight": "400", "dose_mg_per_kg": "5", "concentration_mg_per_ml": "100"},
        format="json",
    )
    assert ok.status_code == 200 and ok.json()["values"]["volume_ml"] == "20"
    bad = api.post("/api/v1/calculators/dose_calc/", {"weight": "0"}, format="json")
    assert bad.status_code == 400 and "error" in bad.json()
    assert api.post("/api/v1/calculators/os_system/", {}, format="json").status_code == 400
    zero = api.post(
        "/api/v1/calculators/mg_to_ml/",
        {"dose_mg": "1", "concentration_mg_per_ml": "0"},
        format="json",
    )
    assert zero.status_code == 400


def test_generic_detail_query_budget(api, django_assert_max_num_queries):
    with django_assert_max_num_queries(20):
        assert api.get("/api/v1/generics/enrofloxacin/").status_code == 200
