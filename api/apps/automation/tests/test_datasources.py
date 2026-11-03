import io
import zipfile
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.automation import datasources, safe_http
from apps.automation.models import DataSource
from apps.ingestion.adapters import ca_dpd, uk_vmd
from apps.pharma.models import Product, ProductRegistration

pytestmark = pytest.mark.django_db

VMD_XML = b"""<?xml version="1.0"?>
<VMD_PIDProducts>
  <CurrentAuthorisedProducts>
    <VMDProductNo>A1</VMDProductNo><Name>Testcillin 10% Injection</Name>
    <MAHolder>Example Pharma Ltd</MAHolder><VMNo>01234/0001</VMNo>
    <ActiveSubstances>Milbemycin Oxime (A3 and A4), Praziquantel</ActiveSubstances>
    <TargetSpecies>Dogs</TargetSpecies><PharmaceuticalForm>Injection</PharmaceuticalForm>
    <SPC_Link>https://example.org/spc.pdf</SPC_Link>
  </CurrentAuthorisedProducts>
  <CurrentAuthorisedProducts>
    <VMDProductNo>A2</VMDProductNo><Name>Testcillin duplicate number</Name>
    <MAHolder>Example Pharma Ltd</MAHolder><VMNo>01234/0001</VMNo>
    <ActiveSubstances>Penicillin</ActiveSubstances>
  </CurrentAuthorisedProducts>
  <SuspendedProducts>
    <VMDProductNo>A3</VMDProductNo><Name>Pausedex</Name><MAHolder>Example Pharma Ltd</MAHolder>
    <VMNo>01234/0002</VMNo><ActiveSubstances>Ivermectin</ActiveSubstances>
  </SuspendedProducts>
  <ExpiredProducts>
    <VMDProductNo>A4</VMDProductNo><Name>Oldex</Name><MAHolder>X Ltd</MAHolder>
    <VMNo>01234/0003</VMNo><ActiveSubstances>Ivermectin</ActiveSubstances>
  </ExpiredProducts>
  <CurrentAuthorisedProducts>
    <VMDProductNo>A5</VMDProductNo><Name>No actives</Name><MAHolder>X Ltd</MAHolder>
    <VMNo>01234/0004</VMNo><ActiveSubstances></ActiveSubstances>
  </CurrentAuthorisedProducts>
</VMD_PIDProducts>"""


def _dpd_zip() -> bytes:
    def csv_line(*cells):
        return ",".join(f'"{c}"' for c in cells) + "\n"

    files = {
        "drug.txt": csv_line("1", "", "Veterinary", "00000001", "TESTVET 10 MG", "", "N", "1", "1")
        + csv_line("2", "", "Human", "00000002", "HUMAN PILL", "", "N", "1", "1"),
        "status.txt": csv_line("1", "N", "APPROVED", "01-JAN-2000", "x", "", "")
        + csv_line("1", "Y", "MARKETED", "01-JAN-2001", "x", "", "")
        + csv_line("2", "Y", "MARKETED", "01-JAN-2001", "x", "", ""),
        "comp.txt": csv_line("1", "", "9", "EXAMPLE VET CO.", "DIN_OWNER")
        + csv_line("2", "", "9", "HUMAN CO", "DIN_OWNER"),
        "ingred.txt": csv_line("1", "5", "ACEPROMAZINE MALEATE", "I", "10", "MG")
        + csv_line("2", "6", "ASPIRIN", "I", "81", "MG"),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buffer.getvalue()


@pytest.fixture
def reference():
    call_command("seed_reference")


def fake_fetch(monkeypatch, status=200, headers=None, body=b"", robots=True):
    calls = []

    def fetch_full(url, **kwargs):
        calls.append((url, kwargs.get("method", "GET")))
        return status, body, url, headers or {}

    monkeypatch.setattr(safe_http, "fetch_full", fetch_full)
    monkeypatch.setattr(safe_http, "allowed_by_robots", lambda *a, **k: robots)
    return calls


# ---------- registry ----------


def test_researched_sources_are_registered_but_cannot_import_yet():
    sources = DataSource.objects.all()
    assert sources.count() >= 11
    assert not sources.filter(import_enabled=True).exists()
    assert not sources.filter(terms_confirmed_at__isnull=False).exists()
    assert set(sources.exclude(importer="").values_list("importer", flat=True)) == {
        "uk-vmd",
        "ca-dpd",
    }


def test_seeded_values_fit_their_columns():
    """SQLite ignores max_length; Postgres (production) would fail the migration instead."""
    for source in DataSource.objects.all():
        for field in DataSource._meta.get_fields():
            limit = getattr(field, "max_length", None)
            value = getattr(source, field.name, None)
            if limit and isinstance(value, str):
                assert len(value) <= limit, (source.slug, field.name, len(value), limit)


def test_import_needs_importer_data_url_and_confirmed_terms():
    source = DataSource.objects.get(slug="uk-vmd-pid")
    source.import_enabled = True
    with pytest.raises(ValidationError, match="terms"):
        source.full_clean()
    source.terms_confirmed_at = timezone.now()
    source.full_clean()  # now fine
    monitor_only = DataSource.objects.get(slug="farad")
    monitor_only.import_enabled = True
    with pytest.raises(ValidationError):
        monitor_only.full_clean()


# ---------- scheduled check ----------


def test_check_records_reachability_and_detects_change(monkeypatch):
    source = DataSource.objects.get(slug="farad")
    fake_fetch(monkeypatch, headers={"etag": '"v1"', "last-modified": "Mon"})
    datasources.check_source(source)
    source.refresh_from_db()
    assert source.last_ok and source.fingerprint and not source.update_available  # baseline
    fake_fetch(monkeypatch, headers={"etag": '"v2"', "last-modified": "Tue"})
    datasources.check_source(source)
    source.refresh_from_db()
    assert source.update_available and source.last_changed_at


def test_failure_counts_but_robots_refusal_does_not(monkeypatch):
    source = DataSource.objects.get(slug="farad")
    fake_fetch(monkeypatch, status=404)
    datasources.check_source(source)
    source.refresh_from_db()
    assert source.last_ok is False and source.consecutive_failures == 1
    assert source.last_error == "HTTP 404"
    fake_fetch(monkeypatch, robots=False)
    datasources.check_source(source)
    source.refresh_from_db()
    assert source.last_ok is None and source.consecutive_failures == 1
    assert "robots" in source.last_error
    fake_fetch(monkeypatch, headers={})
    datasources.check_source(source)
    source.refresh_from_db()
    assert source.last_ok and source.consecutive_failures == 0


def test_network_error_is_recorded_not_raised(monkeypatch):
    def boom(*a, **k):
        raise safe_http.FetchError("Could not fetch: timeout")

    monkeypatch.setattr(safe_http, "fetch_full", boom)
    monkeypatch.setattr(safe_http, "allowed_by_robots", lambda *a, **k: True)
    source = datasources.check_source(DataSource.objects.get(slug="farad"))
    assert source.last_ok is False and "timeout" in source.last_error


def test_openfda_style_json_uses_its_last_updated_date(monkeypatch):
    fake_fetch(
        monkeypatch,
        headers={"content-type": "application/json"},
        body=b'{"meta":{"last_updated":"2026-09-30"},"results":[]}',
    )
    source = datasources.check_source(DataSource.objects.get(slug="us-openfda-animal-events"))
    assert source.fingerprint == "last_updated:2026-09-30"


def test_scheduled_run_respects_interval_and_limit(monkeypatch):
    calls = fake_fetch(monkeypatch)
    total = DataSource.objects.filter(enabled=True).count()
    first = datasources.check_data_sources(limit=3)
    assert first["checked"] == 3 and first["stopped_early"] and first["reachable"] == 3
    second = datasources.check_data_sources(limit=100)
    assert second["checked"] == total - 3  # the three just checked are not due yet
    DataSource.objects.update(last_checked_at=timezone.now() - timedelta(hours=25))
    assert datasources.check_data_sources(limit=100)["checked"] == total
    assert all(method == "HEAD" for _, method in calls)


def test_task_is_registered_for_cron_and_staff():
    from apps.automation import tasks

    assert "data-sources" in tasks.TASKS


# ---------- adapters ----------


def test_uk_vmd_adapter_reshapes_only_what_the_file_states():
    cleaned = uk_vmd.clean_snapshot(VMD_XML)
    assert cleaned.report["rows"] == 2
    assert cleaned.report["skipped_duplicate_number"] == 1
    assert cleaned.report["skipped_ExpiredProducts"] == 1
    assert cleaned.report["skipped_incomplete"] == 1
    first, second = cleaned.rows
    assert first["generic_name"] == "Milbemycin Oxime (A3 and A4) + Praziquantel"
    assert first["registration_status"] == "registered"
    assert "Target species: Dogs" in first["notes"]
    assert second["registration_status"] == "suspended"


def test_uk_vmd_adapter_rejects_entity_bombs():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        b"<VMD_PIDProducts><CurrentAuthorisedProducts><Name>&b;</Name>"
        b"</CurrentAuthorisedProducts></VMD_PIDProducts>"
    )
    with pytest.raises(Exception):  # noqa: B017 - defusedxml raises its own exception types
        uk_vmd.clean_snapshot(bomb)


def test_canada_adapter_keeps_only_veterinary_and_current_status():
    cleaned = ca_dpd.clean_extract(_dpd_zip())
    assert cleaned.report == {"veterinary_products": 1, "rows": 1}
    row = cleaned.rows[0]
    assert row["brand_name"] == "Testvet 10 MG"
    assert row["registration_number"] == "00000001"
    assert row["registration_status"] == "registered"  # the Y (current) row, not the old one
    assert row["composition"] == "Acepromazine Maleate 10 MG"


# ---------- import ----------


def _confirm(slug):
    source = DataSource.objects.get(slug=slug)
    admin = User.objects.create_user("terms-admin", password="x", role=Role.ADMIN)
    datasources.confirm_terms(source, admin)
    source.import_enabled = True
    source.save()
    return source


def test_import_refused_without_confirmed_terms(reference):
    source = DataSource.objects.get(slug="uk-vmd-pid")
    with pytest.raises(datasources.SyncError, match="not enabled"):
        datasources.sync_source(source)
    source.import_enabled = True
    source.save()
    with pytest.raises(datasources.SyncError, match="terms"):
        datasources.sync_source(source)
    assert Product.objects.count() == 0


def test_import_creates_unreviewed_hidden_records_and_is_repeatable(reference, monkeypatch):
    source = _confirm("uk-vmd-pid")
    fake_fetch(monkeypatch, body=VMD_XML, headers={"etag": '"abc"', "last-modified": "Mon"})
    result = datasources.sync_source(source)
    assert result["approved"] == 2
    assert Product.objects.count() == 2
    # never public: only a veterinarian's review can change this
    assert not Product.objects.public().exists()
    assert set(Product.objects.values_list("review_status", flat=True)) == {"imported_unverified"}
    assert ProductRegistration.objects.count() == 2
    assert not ProductRegistration.objects.public().exists()
    source.refresh_from_db()
    assert source.last_imported_at and not source.update_available
    assert source.imported_fingerprint
    again = datasources.sync_source(source)
    assert again["staged"] == 0 and Product.objects.count() == 2  # same file: nothing new


def test_import_refuses_an_unreadable_or_empty_file(reference, monkeypatch):
    source = _confirm("uk-vmd-pid")
    fake_fetch(monkeypatch, body=b"<html>moved</html>")
    with pytest.raises(datasources.SyncError, match="no usable rows"):
        datasources.sync_source(source)
    fake_fetch(monkeypatch, body=b"not xml at all")
    with pytest.raises(datasources.SyncError, match="could not be read"):
        datasources.sync_source(source)
    fake_fetch(monkeypatch, status=500)
    with pytest.raises(datasources.SyncError, match="HTTP 500"):
        datasources.sync_source(source)
    assert Product.objects.count() == 0


def test_canada_import_end_to_end(reference, monkeypatch):
    source = _confirm("ca-health-canada-dpd")
    fake_fetch(monkeypatch, body=_dpd_zip(), headers={"etag": '"z"'})
    assert datasources.sync_source(source)["approved"] == 1
    assert Product.objects.get().registrations.get().country.iso2 == "CA"


def test_sync_command_checks_then_imports_only_changed_importable_sources(
    reference, monkeypatch, capsys
):
    _confirm("uk-vmd-pid")
    fake_fetch(monkeypatch, body=VMD_XML, headers={"etag": '"abc"', "last-modified": "Mon"})
    call_command("sync_data_sources")
    assert Product.objects.count() == 2
    out = capsys.readouterr().out
    assert "uk-vmd-pid" in out and "farad: ok" in out
    call_command("sync_data_sources", "--check-only")  # nothing changed: no re-import
    assert Product.objects.count() == 2


def test_staff_panel_lists_sources_with_status_and_import_state(monkeypatch):
    fake_fetch(monkeypatch)
    datasources.check_data_sources(limit=100)
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    client = APIClient()
    client.force_authenticate(editor)
    rows = client.get("/api/v1/staff/automation/").json()["data_sources"]
    by_name = {r["name"]: r for r in rows}
    uk = by_name["UK VMD Product Information Database"]
    assert uk["reachable"] is True and uk["can_import"] and not uk["terms_confirmed"]
    assert by_name["FARAD (withdrawal interval guidance)"]["can_import"] is False
    anonymous = APIClient().get("/api/v1/staff/automation/")
    assert anonymous.status_code in (401, 403)
