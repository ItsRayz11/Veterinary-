import pytest
from django.core.management import call_command

from apps.countries.models import Country
from apps.ingestion import services
from apps.ingestion.adapters import common, uk_vmd
from apps.pharma.models import ProductRegistration, RegistrationSpecies
from apps.species.mapping import species_slug, split_labels

XML = b"""<?xml version="1.0"?>
<VMD_PIDProducts>
  <CurrentAuthorisedProducts>
    <VMDProductNo>A1</VMDProductNo><Name>Pigmox Premix</Name><MAHolder>Acme Vet Ltd</MAHolder>
    <VMNo>00001/0001</VMNo><ActiveSubstances>Amoxicillin</ActiveSubstances>
    <TargetSpecies>Pigs, Honey bees</TargetSpecies><TherapeuticGroup>Antimicrobial</TherapeuticGroup>
  </CurrentAuthorisedProducts>
  <CurrentAuthorisedProducts>
    <VMDProductNo>A2</VMDProductNo><Name>Pigmox Premix</Name><MAHolder>Acme Vet Ltd</MAHolder>
    <VMNo>00001/0002</VMNo><ActiveSubstances>Amoxicillin</ActiveSubstances>
    <TargetSpecies>Cattle</TargetSpecies>
  </CurrentAuthorisedProducts>
  <ExpiredProducts>
    <VMDProductNo>A3</VMDProductNo><Name>Old</Name><MAHolder>Acme Vet Ltd</MAHolder>
    <VMNo>00001/0009</VMNo><ActiveSubstances>Amoxicillin</ActiveSubstances>
    <TargetSpecies>Dogs</TargetSpecies>
  </ExpiredProducts>
</VMD_PIDProducts>"""


def test_mapping_is_exact():
    assert species_slug("Pigs") == "swine"
    assert species_slug("Trout - Golden/Rainbow/Redband/Steelhead") == "fish"
    assert species_slug("Honey bees") is None
    assert species_slug("Exotic Animal") is None
    assert split_labels("Cattle, Pigs, cattle") == ["Cattle", "Pigs"]


def test_adapter_reads_target_species_and_expired():
    cleaned = uk_vmd.clean_snapshot(XML)
    assert [r["target_species"] for r in cleaned.rows][0] == [
        {"label": "Pigs"},
        {"label": "Honey bees"},
    ]
    assert cleaned.expired_numbers == ["00001/0009"]


@pytest.mark.django_db
def test_import_attaches_species_per_authorisation_and_reconciles():
    call_command("seed_reference")
    country = Country.objects.get(iso2="GB")
    user = services.import_user()
    cleaned = uk_vmd.clean_snapshot(XML)
    batch = services.stage_batch(
        user=user,
        country=country,
        source_data={"title": "VMD test", "publisher": "VMD", "license_note": "OGL v3.0"},
        csv_text=common.to_csv(cleaned.rows),
    )
    services.approve_clean(batch, user)
    first = ProductRegistration.objects.get(registration_number="00001/0001")
    assert {
        (t.label, t.species.slug if t.species else None) for t in first.target_species.all()
    } == {
        ("Pigs", "swine"),
        ("Honey bees", None),
    }
    # The second authorisation of the same brand was flagged as a duplicate by the importer.
    assert not ProductRegistration.objects.filter(registration_number="00001/0002").exists()

    from apps.sources.models import Source

    src = Source.objects.first()
    rest = [r for r in cleaned.rows if r["registration_number"] != "00001/0001"]
    out = services.reconcile_registrations(country, src, rest, ["00001/0001"], user)
    assert out["registrations_added"] == 1
    second = ProductRegistration.objects.get(registration_number="00001/0002")
    assert second.product_id == first.product_id
    assert [t.species.slug for t in second.target_species.all()] == ["cattle"]
    first.refresh_from_db()
    assert first.status == "expired" and out["status_changed"] == 1
    # Idempotent: a second run changes nothing.
    again = services.reconcile_registrations(country, src, rest, ["00001/0001"], user)
    assert again == {
        "status_changed": 0,
        "species_added": 0,
        "registrations_added": 0,
        "needs_review": 0,
    }
    assert RegistrationSpecies.objects.count() == 3


@pytest.mark.django_db
def test_species_endpoint_lists_authorised_medicines_not_by_ingredient_alone(client):
    call_command("seed_reference")
    country = Country.objects.get(iso2="GB")
    user = services.import_user()
    cleaned = uk_vmd.clean_snapshot(XML)
    batch = services.stage_batch(
        user=user,
        country=country,
        source_data={"title": "VMD test", "publisher": "VMD", "license_note": "OGL v3.0"},
        csv_text=common.to_csv(cleaned.rows),
    )
    services.approve_clean(batch, user)
    swine = client.get("/api/v1/species/swine/").json()
    assert [m["slug"] for m in swine["authorized_medicines"]] == ["amoxicillin"]
    assert swine["authorized_medicines"][0]["unverified"] is True
    # Same ingredient, but no authorisation names sheep: nothing is implied.
    assert client.get("/api/v1/species/sheep/").json()["authorized_medicines"] == []
    assert swine["generics"] == []  # doses stay separate


@pytest.mark.django_db
def test_rollback_removes_unreviewed_import_and_is_dry_run_by_default(capsys):
    from django.core.management import call_command

    from apps.automation.models import DataSource
    from apps.pharma.models import Product
    from apps.sources.models import Source

    call_command("seed_reference")
    ds = DataSource.objects.get(slug="uk-vmd-pid")
    country = Country.objects.get(iso2="GB")
    user = services.import_user()
    cleaned = uk_vmd.clean_snapshot(XML)
    batch = services.stage_batch(
        user=user,
        country=country,
        source_data={"title": ds.name, "publisher": ds.publisher, "license_note": "OGL v3.0"},
        csv_text=common.to_csv(cleaned.rows),
    )
    services.approve_clean(batch, user)
    assert Product.objects.count() == 1
    call_command("rollback_import", "--source", ds.slug, "--since", "2000-01-01")
    assert Product.objects.count() == 1  # dry run
    call_command("rollback_import", "--source", ds.slug, "--since", "2000-01-01", "--apply")
    assert Product.objects.count() == 0 and ProductRegistration.objects.count() == 0
    assert Source.objects.exists()


@pytest.mark.django_db
def test_source_problems_flags_failures_and_stale_imports():
    from django.utils import timezone

    from apps.automation import datasources
    from apps.automation.models import DataSource

    ds = DataSource.objects.get(slug="uk-vmd-pid")
    assert datasources.source_problems() == []
    ds.consecutive_failures, ds.last_error = 4, "HTTP 500"
    ds.import_enabled, ds.last_imported_at = True, timezone.now() - timezone.timedelta(days=30)
    ds.save()
    problems = datasources.source_problems()
    assert len(problems) == 2 and all(p.startswith("uk-vmd-pid") for p in problems)
