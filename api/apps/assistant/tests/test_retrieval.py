"""Retrieval must find the right drugs by name, synonym or brand, and its cost must not depend on
how large the catalogue is."""

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.assistant import retrieval
from apps.pharma.models import Generic, GenericSynonym, Product


@pytest.fixture
def world(db):
    call_command("seed_dev_catalog")  # enrofloxacin + two brands, development data (public)
    return Generic.objects.get(slug="enrofloxacin")


def slugs(question):
    return [g.slug for g in retrieval.find_generics(question)]


def test_finds_by_generic_name_case_and_punctuation_insensitively(world):
    assert slugs("What is the dose of ENROFLOXACIN, in cattle?") == ["enrofloxacin"]
    assert slugs("enrofloxacin") == ["enrofloxacin"]


def test_finds_by_synonym_and_by_brand_name(world):
    GenericSynonym.objects.create(generic=world, synonym="Baytril generic")
    assert slugs("tell me about baytril generic please") == ["enrofloxacin"]
    brand = Product.objects.filter(generic=world).first()
    assert slugs(f"Is {brand.brand_name} safe?") == ["enrofloxacin"]


def test_matches_whole_words_only(world):
    assert slugs("What about enrofloxacinum salts?") == []
    assert slugs("nonenrofloxacin") == []


def test_multi_word_names_are_found(world):
    Generic.objects.create(name="Amoxicillin Clavulanic Acid", is_development_data=True)
    assert slugs("dose of amoxicillin clavulanic acid for dogs") == ["amoxicillin-clavulanic-acid"]
    assert slugs("amoxicillin alone") == []


def test_hidden_records_are_never_found(world, settings):
    settings.SHOW_DEVELOPMENT_DATA = False
    assert slugs("enrofloxacin") == []


def test_at_most_three_drugs_and_empty_questions(world):
    for name in ("Alphacillin", "Betacillin", "Gammacillin", "Deltacillin"):
        Generic.objects.create(name=name, is_development_data=True)
    found = slugs("alphacillin betacillin gammacillin deltacillin enrofloxacin")
    assert len(found) == retrieval.MAX_GENERICS
    assert slugs("") == [] and slugs("!!! ???") == []


def test_query_count_does_not_grow_with_the_catalogue(world):
    question = "What is the dose of enrofloxacin in cattle?"
    with CaptureQueriesContext(connection) as small:
        retrieval.find_generics(question)
    Generic.objects.bulk_create(
        [
            Generic(
                name=f"Filler {i}",
                normalized_name=f"filler {i}",
                slug=f"filler-{i}",
                is_development_data=True,
            )
            for i in range(300)
        ]
    )
    with CaptureQueriesContext(connection) as large:
        found = retrieval.find_generics(question)
    assert [g.slug for g in found] == ["enrofloxacin"]
    assert len(large) == len(small) and len(large) <= 4  # fixed cost: 3 lookups


def test_very_long_questions_stay_bounded(world):
    question = "enrofloxacin " + "word " * 400
    with CaptureQueriesContext(connection) as q:
        assert slugs(question) == ["enrofloxacin"]
    assert len(q) <= 4
