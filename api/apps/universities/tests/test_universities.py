import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.core.models import ReviewStatus
from apps.countries.models import Country
from apps.education.models import PastPaper
from apps.universities import importer
from apps.universities.models import University


@pytest.fixture
def pk(db):
    return Country.objects.create(iso2="PK", slug="pakistan", name="Pakistan", currency_code="PKR")


def fake_fetch(host, params):
    """Minimal stand-in for the Wikipedia and Wikidata APIs."""
    action = params.get("action")
    if params.get("list") == "categorymembers":
        return {
            "query": {
                "categorymembers": [
                    {"title": "University of Veterinary and Animal Sciences"},
                    {"title": "List of veterinary schools"},
                    {"title": "Category:Something"},
                    {"title": "Agricultural Training Institute (Peshawar)"},
                    {"title": "Some Unrelated College"},
                ]
            }
        }
    if params.get("prop") == "extracts|pageprops|pageimages|info":
        pages = {
            "1": {
                "title": "University of Veterinary and Animal Sciences",
                "extract": "A public veterinary university in Lahore.",
                "pageprops": {"wikibase_item": "Q1"},
                "pageimage": "Uvas_logo.png",
                "fullurl": "https://en.wikipedia.org/wiki/UVAS",
            },
            "2": {
                "title": "Some Unrelated College",
                "extract": "A college of arts.",
                "pageprops": {"wikibase_item": "Q2"},
            },
        }
        return {"query": {"pages": pages}}
    if action == "wbgetentities" and params.get("props") == "claims":
        return {
            "entities": {
                "Q1": {
                    "claims": {
                        "P856": [{"mainsnak": {"datavalue": {"value": "https://uvas.edu.pk"}}}],
                        "P625": [
                            {
                                "mainsnak": {
                                    "datavalue": {"value": {"latitude": 31.5, "longitude": 74.3}}
                                }
                            }
                        ],
                        "P571": [
                            {"mainsnak": {"datavalue": {"value": {"time": "+1882-00-00T00"}}}}
                        ],
                        "P131": [{"mainsnak": {"datavalue": {"value": {"id": "Q9"}}}}],
                    }
                }
            }
        }
    if action == "wbgetentities" and params.get("props") == "labels":
        return {"entities": {"Q9": {"labels": {"en": {"value": "Lahore"}}}}}
    if params.get("prop") == "imageinfo":
        return {
            "query": {
                "pages": {
                    "1": {
                        "imageinfo": [
                            {
                                "thumburl": "https://upload.wikimedia.org/thumb/x.png",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:X.png",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "Artist": {"value": '<a href="#">Jane Doe</a>'},
                                    "LicenseUrl": {"value": "https://creativecommons.org/x"},
                                },
                            }
                        ]
                    }
                }
            }
        }
    raise AssertionError(f"unexpected call {host} {params}")


def test_license_filter():
    assert importer.is_open_license("CC BY-SA 4.0")
    assert importer.is_open_license("CC0")
    assert importer.is_open_license("Public domain")
    assert not importer.is_open_license("Non-free logo")
    assert not importer.is_open_license("")


def test_relevance_rules():
    assert importer.is_relevant(
        "Ontario Veterinary College", "The Ontario Veterinary College is a school."
    )
    assert importer.is_relevant(
        "Colorado State University",
        "Colorado State University hosts a veterinary teaching hospital.",
    )
    # Not an institution, or the first sentence is about something else.
    assert not importer.is_relevant(
        "American Veterinary Medical Association", "A professional body of veterinarians."
    )
    assert not importer.is_relevant(
        "Middlesex University",
        "Middlesex University is a medical school. It once ran a veterinary school.",
    )


def test_collect_filters_noise_and_keeps_provenance():
    rows = importer.collect(fake_fetch, "PK")
    assert [r["name"] for r in rows] == ["University of Veterinary and Animal Sciences"]
    r = rows[0]
    assert r["website"] == "https://uvas.edu.pk"
    assert r["city"] == "Lahore"
    assert r["founded_year"] == 1882
    assert r["image"]["credit"] == "Jane Doe"
    assert r["image"]["license"] == "CC BY-SA 4.0"


def test_non_free_image_is_dropped():
    def fetch(host, params):
        return {
            "query": {
                "pages": {
                    "1": {
                        "imageinfo": [
                            {"url": "u", "extmetadata": {"LicenseShortName": {"value": "Fair use"}}}
                        ]
                    }
                }
            }
        }

    assert importer.open_image(fetch, "X.png") is None


def test_import_command_is_unreviewed_and_never_overwrites_reviewed(pk, monkeypatch):
    monkeypatch.setattr(importer, "api_fetch", fake_fetch)
    call_command("import_universities", "--country", "PK")
    u = University.objects.get()
    assert u.review_status == ReviewStatus.IMPORTED_UNVERIFIED
    assert u.source_license.startswith("CC BY-SA")
    assert u.image_credit == "Jane Doe"

    University.objects.update(review_status=ReviewStatus.EXPERT_REVIEWED, summary="Edited by hand")
    call_command("import_universities", "--country", "PK")
    u.refresh_from_db()
    assert u.summary == "Edited by hand"


def test_api_lists_unreviewed_labelled_and_hides_unlisted(pk, settings):
    settings.SHOW_UNVERIFIED_IMPORTS = True
    University.objects.create(
        name="UVAS", country=pk, review_status=ReviewStatus.IMPORTED_UNVERIFIED, city="Lahore"
    )
    University.objects.create(name="Hidden", country=pk)  # needs_verification
    PastPaper.objects.create(
        university="UVAS",
        degree="DVM",
        course="Anatomy",
        year=2024,
        legal_source_url="https://example.org/p.pdf",
        license_note="Published by owner",
        is_published=True,
    )
    c = APIClient()
    rows = c.get("/api/v1/universities/").json()["results"]
    assert [r["name"] for r in rows] == ["UVAS"]
    assert rows[0]["status"]["is_unverified_import"] is True
    assert c.get("/api/v1/universities/?country=in").json()["results"] == []
    detail = c.get("/api/v1/universities/uvas/").json()
    assert detail["past_papers"][0]["course"] == "Anatomy"
    assert c.get("/api/v1/universities/hidden/").status_code == 404


def test_unreviewed_hidden_when_setting_off(pk, settings):
    settings.SHOW_UNVERIFIED_IMPORTS = False
    University.objects.create(
        name="UVAS", country=pk, review_status=ReviewStatus.IMPORTED_UNVERIFIED
    )
    assert APIClient().get("/api/v1/universities/").json()["results"] == []


def test_sitemap_slug_lists(pk, settings):
    settings.SHOW_UNVERIFIED_IMPORTS = True
    Company.objects.create(
        name="Acme Vet", country=pk, review_status=ReviewStatus.IMPORTED_UNVERIFIED
    )
    Company.objects.create(name="Draft Co", country=pk)
    rows = APIClient().get("/api/v1/companies/").json()["results"]
    assert [r["slug"] for r in rows] == ["acme-vet"]
    assert "updated_at" in rows[0]
    assert rows[0]["unverified"] is True
    assert APIClient().get("/api/v1/products/").status_code == 200
