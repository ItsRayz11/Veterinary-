import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.pharma.models import DrugClass, Generic


@pytest.fixture
def api(db):
    call_command("seed_dev_catalog")
    return APIClient()


@pytest.fixture
def classed(api):
    """Enrofloxacin placed under Antibacterials > Fluoroquinolones (test-only classes)."""
    parent = DrugClass.objects.create(name="Antibacterials")
    leaf = DrugClass.objects.create(name="Fluoroquinolones", parent=parent)
    generic = Generic.objects.get(slug="enrofloxacin")
    generic.drug_class = leaf
    generic.save()
    return parent, leaf


def test_drug_class_tree_counts_and_detail_include_descendants(api, classed):
    parent, leaf = classed
    rows = {r["slug"]: r for r in api.get("/api/v1/drug-classes/").json()}
    assert rows[leaf.slug]["generic_count"] == 1
    assert rows[parent.slug]["generic_count"] == 1  # includes its sub-class, like the detail page
    top = api.get(f"/api/v1/drug-classes/{parent.slug}/").json()
    assert [g["slug"] for g in top["generics"]] == ["enrofloxacin"]
    assert [c["slug"] for c in top["children"]] == [leaf.slug]
    detail = api.get(f"/api/v1/drug-classes/{leaf.slug}/").json()
    assert [a["slug"] for a in detail["ancestors"]] == [parent.slug]
    assert api.get("/api/v1/drug-classes/nope/").status_code == 404


def test_drug_class_hides_generics_when_dev_data_hidden(api, classed, settings):
    settings.SHOW_DEVELOPMENT_DATA = False
    slug = classed[0].slug
    assert api.get(f"/api/v1/drug-classes/{slug}/").json()["generics"] == []


def test_species_page_lists_only_generics_with_public_doses(api):
    data = api.get("/api/v1/species/dog/").json()
    assert data["generics"] == []  # the dev catalogue contains no dose regimens
    assert api.get("/api/v1/species/nope/").status_code == 404


def test_country_page_lists_public_registrations_only(api, settings):
    data = api.get("/api/v1/countries/pk/").json()
    assert data["iso2"] == "PK" and len(data["products"]) == 2
    settings.SHOW_DEVELOPMENT_DATA = False
    assert api.get("/api/v1/countries/PK/").json()["products"] == []
    assert api.get("/api/v1/countries/ZZ/").status_code == 404
