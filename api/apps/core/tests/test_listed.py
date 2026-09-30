"""Unreviewed imports are listed (labelled) in the catalogue, never in clinical features."""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.core.models import ReviewStatus
from apps.countries.models import Country
from apps.pharma.models import Generic, Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def imported(db):
    from django.core.management import call_command

    call_command("seed_reference")
    pk = Country.objects.get(iso2="PK")
    g = Generic.objects.create(
        name="Importedcillin", review_status=ReviewStatus.IMPORTED_UNVERIFIED
    )
    c = Company.objects.create(
        name="Import Co", country=pk, review_status=ReviewStatus.IMPORTED_UNVERIFIED
    )
    p = Product.objects.create(
        brand_name="Importo",
        generic=g,
        manufacturer=c,
        review_status=ReviewStatus.IMPORTED_UNVERIFIED,
    )
    return g, c, p


def test_listed_includes_imports_but_public_does_not(imported):
    g, c, p = imported
    assert g in Generic.objects.listed() and g not in Generic.objects.public()
    assert c in Company.objects.listed() and p in Product.objects.listed()
    assert not g.is_public


@override_settings(SHOW_UNVERIFIED_IMPORTS=False)
def test_switch_hides_them_again(imported):
    g, c, p = imported
    assert g not in Generic.objects.listed() and p not in Product.objects.listed()


def test_needs_verification_records_stay_hidden(imported):
    g, *_ = imported
    g.review_status = ReviewStatus.NEEDS_VERIFICATION
    g.save()
    assert g not in Generic.objects.listed()


@override_settings(SHOW_DEVELOPMENT_DATA=False)
def test_development_data_is_not_listed_as_an_import(imported):
    g, *_ = imported
    g.is_development_data = True
    g.save()
    assert g not in Generic.objects.listed()


def test_api_shows_labelled_unverified_records(imported):
    g, c, p = imported
    api = APIClient()
    detail = api.get(f"/api/v1/generics/{g.slug}/").json()
    assert detail["status"]["is_unverified_import"] is True
    assert detail["status"]["code"] == "imported_unverified"
    assert api.get(f"/api/v1/companies/{c.slug}/").status_code == 200
    found = api.get("/api/v1/search/?q=Importo").json()
    assert any(x["name"] == "Importo" for x in found["products"])


def test_clinical_features_and_assistant_never_see_them(imported):
    from apps.assistant import retrieval

    g, *_ = imported
    assert retrieval.Generic.objects.public().filter(pk=g.pk).count() == 0


def test_a_reviewer_can_still_promote_them(imported):
    from django.contrib.contenttypes.models import ContentType

    from apps.accounts.models import Role, User
    from apps.core.review import set_review_status
    from apps.sources.models import Source, SourceLink

    g, *_ = imported
    src = Source.objects.create(source_type="other", title="Label", url="https://example.org")
    SourceLink.objects.create(
        source=src, content_type=ContentType.objects.get_for_model(g), object_id=g.pk
    )
    vet = User.objects.create_user("vet", password="x", role=Role.VET_REVIEWER)
    set_review_status(g, ReviewStatus.VERIFIED, vet)
    assert g in Generic.objects.public()


def test_country_page_lists_unverified_imports_of_that_country_only(imported):
    _, c, p = imported
    api = APIClient()
    pk = api.get("/api/v1/countries/PK/").json()
    row = next(x for x in pk["products"] if x["slug"] == p.slug)
    assert row["status"]["is_unverified_import"] is True and row["countries"] == []
    assert all(x["slug"] != p.slug for x in api.get("/api/v1/countries/IN/").json()["products"])
