"""Slugs must fit their columns: PostgreSQL rejects values SQLite silently accepts."""

import pytest

from apps.core.text import unique_slug
from apps.education.models import Subject, Topic
from apps.pharma.models import Generic, Product

LONG = "Amoxicillin Trihydrate Clavulanic Potassium Gentamicin Sulphate Colistin Neomycin Extra"


def test_long_names_get_slugs_within_the_column_limit(db):
    limit = Generic._meta.get_field("slug").max_length
    slug = unique_slug(Generic, LONG)
    assert 0 < len(slug) <= limit and slug.startswith("amoxicillin-trihydrate")


def test_colliding_long_names_stay_unique_and_within_the_limit(db):
    limit = Generic._meta.get_field("slug").max_length
    a = Generic.objects.create(name=LONG)
    b = Generic.objects.create(name=LONG + " two")  # same first 40 characters once truncated
    c = Generic.objects.create(name=LONG + " three")
    slugs = {a.slug, b.slug, c.slug}
    assert len(slugs) == 3 and all(len(s) <= limit for s in slugs)


def test_suffix_never_pushes_a_slug_over_the_limit(db):
    limit = Generic._meta.get_field("slug").max_length
    for i in range(12):
        Generic.objects.create(name=f"{LONG} variant {i}")
    assert all(len(g.slug) <= limit for g in Generic.objects.all())


def test_products_and_topics_respect_their_limits_too(db):
    assert Product._meta.get_field("slug").max_length >= len(unique_slug(Product, LONG * 2))
    subject = Subject.objects.create(name="Pharmacology")
    topic = Topic.objects.create(subject=subject, name=LONG * 3)
    assert len(topic.slug) <= Topic._meta.get_field("slug").max_length


@pytest.mark.parametrize("weird", ["", "!!!", "   ", "---"])
def test_empty_or_symbol_only_names_still_get_a_slug(db, weird):
    assert unique_slug(Generic, weird)
