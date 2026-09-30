"""Regressions found while loading the real DRAP files."""

import pytest
from django.core.exceptions import ValidationError

from apps.ingestion import services
from apps.ingestion.adapters import drap
from apps.ingestion.tests.test_drap_adapters import APPLICATIONS, env, load  # noqa: F401
from apps.pharma.models import Generic


def test_a_composition_column_can_never_overwrite_the_generic_name():
    """An old alias mapped 'composition' onto 'generic_name', so the composition text silently
    replaced the generic's name."""
    text = (
        "brand_name,generic_name,manufacturer,composition\n"
        "Zed,Enrofloxacin,Acme,Each ml contains: Enrofloxacin 100 mg\n"
    )
    row = services.parse_csv(text)[0]
    assert row["generic_name"] == "Enrofloxacin"
    assert row["composition"].startswith("Each ml")


def test_two_columns_meaning_the_same_field_are_refused():
    with pytest.raises(ValidationError, match="both mean"):
        services.parse_csv("brand,product_name,generic_name,manufacturer\nA,B,C,D\n")


def test_generic_names_come_from_ingredients_not_from_composition_text(env):  # noqa: F811
    load(env, drap.clean_vet_applications(APPLICATIONS))
    names = set(Generic.objects.values_list("name", flat=True))
    assert "Ivermectin" in names and "Doramectin" in names
    assert not any("Each" in n or "Contains" in n for n in names)
