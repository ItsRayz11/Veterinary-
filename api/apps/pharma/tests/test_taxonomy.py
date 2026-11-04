import pytest
from django.core.management import call_command

from apps.pharma import taxonomy
from apps.pharma.models import DrugClass, Generic


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Amoxicillin", "Penicillins"),
        ("Amoxicillin (amoxicillin Trihydrate)", "Penicillins"),
        ("Amoxicillin Trihydrate", "Penicillins"),
        ("Enrofloxacin", "Fluoroquinolones"),
        ("Amoxicillin + Colistin", None),
        ("Unknownium", None),
    ],
)
def test_class_for(name, expected):
    assert taxonomy.class_for(name) == expected


@pytest.mark.django_db
def test_bootstrap_files_generics_and_is_idempotent():
    Generic.objects.create(name="Amoxicillin")
    Generic.objects.create(name="Mystery blend")
    for _ in range(2):
        call_command("bootstrap_public_data", "--skip-universities")
    assert Generic.objects.get(name="Amoxicillin").drug_class.name == "Penicillins"
    assert Generic.objects.get(name="Mystery blend").drug_class is None
    assert DrugClass.objects.filter(name="Penicillins").count() == 1
