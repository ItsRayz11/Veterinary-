import io
import time
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
        "vet.txt": csv_line("1", "Dogs", "Puppies")
        + csv_line("1", "Cats", "")
        + csv_line("2", "Humans", ""),
        "route.txt": csv_line("1", "9", "ORAL", "x") + csv_line("1", "10", "INTRAVENOUS", "x"),
        "form.txt": csv_line("1", "3", "TABLET", "x"),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch):
    monkeypatch.setattr(datasources, "RETRY_BACKOFF", (0, 0))


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
        "us-dailymed",
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
    # joined by DRUG_CODE: species (never the human row's), routes, form, provenance, status date
    assert row["target_species"] == [{"label": "Dogs (Puppies)"}, {"label": "Cats"}]
    assert "Route: Oral, Intravenous." in row["notes"]
    assert "Form: Tablet." in row["notes"]
    assert "Health Canada status: Marketed (since 01-JAN-2001)." in row["notes"]
    assert "DRUG_CODE 1" in row["notes"]


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buffer.getvalue()


def _vet_files(**extra) -> dict[str, str]:
    files = {
        "drug.txt": '"1","","Veterinary","111","VETONE","","N","1","1","02-NOV-2026"\n',
        "status.txt": '"1","Y","CANCELLED POST MARKET","05-MAY-2020","x","",""\n',
        "comp.txt": '"1","","9","ACME VET"\n',
        "ingred.txt": '"1","5","TILMICOSIN","I","300","MG"\n',
    }
    files.update(extra)
    return files


def test_canada_adapter_keeps_original_status_and_dates_and_flags_missing_species():
    cleaned = ca_dpd.clean_extract(_zip(_vet_files()))
    row = cleaned.rows[0]
    assert row["registration_status"] == "withdrawn"
    assert "Cancelled Post Market (since 05-MAY-2020)" in row["notes"]
    assert "record updated 02-NOV-2026" in row["notes"]
    assert row["target_species"] == []  # optional files absent: nothing invented
    assert cleaned.report["rows_without_species"] == 1


def test_canada_adapter_accepts_header_rows_and_variant_file_names():
    files = {
        "drug_ap.txt": '"DRUG_CODE","X"\n' + _vet_files()["drug.txt"],
        "status_ap.txt": _vet_files()["status.txt"].replace("CANCELLED POST MARKET", "APPROVED"),
        "comp_ap.txt": _vet_files()["comp.txt"],
        "ingred_ap.txt": _vet_files()["ingred.txt"],
    }
    cleaned = ca_dpd.clean_extract(_zip(files))
    assert cleaned.rows[0]["registration_status"] == "registered"


def test_canada_adapter_prevents_duplicates_and_unknown_status_stays_unknown():
    files = _vet_files(
        **{
            "drug.txt": _vet_files()["drug.txt"]
            + '"1","","Veterinary","111","DUP CODE","","N","1","1","x"\n'
            + '"2","","Veterinary","111","DUP DIN","","N","1","1","x"\n',
            "status.txt": _vet_files()["status.txt"].replace(
                "CANCELLED POST MARKET", "SOMETHING NEW"
            )
            + '"2","Y","MARKETED","x","x"\n',
            "comp.txt": _vet_files()["comp.txt"] + '"2","","9","ACME"\n',
            "ingred.txt": _vet_files()["ingred.txt"] + '"2","5","X","I","1","MG"\n',
        }
    )
    cleaned = ca_dpd.clean_extract(_zip(files))
    assert len(cleaned.rows) == 1
    assert cleaned.rows[0]["registration_status"] == "unknown"
    assert cleaned.report["skipped_duplicate_drug_code"] == 1
    assert cleaned.report["skipped_duplicate_din"] == 1
    assert cleaned.report["unmapped_status"] == 1


@pytest.mark.parametrize(
    "data",
    [
        b"not a zip",
        _zip({"drug.txt": "x"}),  # required files missing
        _zip({**_vet_files(), "drug.txt": '"abc","","Human","1","X"\n'}),  # no vet products
        _zip({**_vet_files(), "drug.txt": '"x","y"\n'}),  # wrong layout
    ],
)
def test_canada_adapter_rejects_unusable_archives(data):
    with pytest.raises(ca_dpd.ExtractError):
        ca_dpd.clean_extract(data)


def test_canada_source_stays_disabled_and_unconfirmed():
    source = DataSource.objects.get(slug="ca-health-canada-dpd")
    assert not source.import_enabled and source.terms_confirmed_at is None


def test_download_retries_server_errors_then_succeeds(monkeypatch):
    monkeypatch.setattr(datasources, "RETRY_BACKOFF", (0, 0))
    responses = iter([(503, b"", "u", {}), (200, b"ok", "u", {"etag": "e"})])
    monkeypatch.setattr(safe_http, "fetch_full", lambda *a, **k: next(responses))
    status, body, _headers = datasources._download("http://x", time.monotonic() + 60, print)
    assert (status, body) == (200, b"ok")


def test_download_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr(datasources, "RETRY_BACKOFF", (0, 0))
    calls = []

    def fetch(*a, **k):
        calls.append(1)
        return 403, b"", "u", {}

    monkeypatch.setattr(safe_http, "fetch_full", fetch)
    assert datasources._download("http://x", time.monotonic() + 60, print)[0] == 403
    assert len(calls) == 1


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


def test_a_paused_source_is_not_checked_and_never_fails_the_daily_alert(monkeypatch, capsys):
    """An admin pauses an unreachable source (for example a regulator site that times out) so the
    daily sync stops failing; resuming it brings the checks and the alert back."""
    source = DataSource.objects.get(slug="farad")
    DataSource.objects.filter(pk=source.pk).update(
        consecutive_failures=datasources.FAILURES_BEFORE_ALERT + 5, last_error="TimeoutError"
    )
    assert any(p.startswith("farad:") for p in datasources.source_problems())

    DataSource.objects.filter(pk=source.pk).update(paused=True)
    assert not any(p.startswith("farad:") for p in datasources.source_problems())
    calls = fake_fetch(monkeypatch)
    call_command("sync_data_sources", "--check-only")
    assert "farad:" not in capsys.readouterr().out
    urls = {u for u in (source.landing_url, source.data_url) if u}
    assert urls and not any(url in urls for url, _ in calls)

    DataSource.objects.filter(pk=source.pk).update(paused=False)
    assert any(p.startswith("farad:") for p in datasources.source_problems())
