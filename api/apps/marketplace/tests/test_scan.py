import base64
import json
import struct

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.marketplace import scan
from apps.marketplace.models import Catalog3D, Supplier


def glb(doc: dict | None = None, extra: bytes = b"") -> bytes:
    payload = json.dumps(doc if doc is not None else {"asset": {"version": "2.0"}}).encode()
    payload += b" " * (-len(payload) % 4) + extra
    body = struct.pack("<I", len(payload)) + b"JSON" + payload
    return b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body


def test_clean_model_passes_builtin_scan():
    assert scan.inspect_glb(glb())[0] == scan.CLEAN


@pytest.mark.parametrize(
    "doc",
    [
        {"asset": {"version": "2.0"}, "buffers": [{"uri": "https://evil.example/x.bin"}]},
        {"asset": {"version": "2.0"}, "images": [{"uri": "data:text/html;base64,AAAA"}]},
        {"asset": {"version": "2.0"}, "extensionsRequired": ["KHR_draco_mesh_compression"]},
        {"asset": {"version": "2.0"}, "extensionsUsed": ["EXT_meshopt_compression"]},
    ],
)
def test_external_uris_script_data_and_remote_decoders_are_flagged(doc):
    assert scan.inspect_glb(glb(doc))[0] == scan.SUSPICIOUS


def test_script_markers_flagged_and_garbage_json_flagged():
    assert scan.inspect_glb(glb(extra=b"<script>alert(1)</script>"))[0] == scan.SUSPICIOUS
    bad = b"glTF" + struct.pack("<II", 2, 12 + 8 + 4) + struct.pack("<I", 4) + b"JSON" + b"{{{{"
    assert scan.inspect_glb(bad)[0] == scan.SUSPICIOUS


def test_optional_engines_are_off_without_configuration(monkeypatch):
    monkeypatch.delenv("CLAMD_HOST", raising=False)
    monkeypatch.delenv("VIRUSTOTAL_API_KEY", raising=False)
    assert scan.clamav(b"x") is None and scan.virustotal("0" * 64) is None


def test_engine_verdicts_combine_worst_wins(monkeypatch):
    monkeypatch.setattr(scan, "clamav", lambda d: (scan.INFECTED, "ClamAV: Eicar"))
    status, detail, digest = scan.scan(glb())
    assert status == scan.INFECTED and "Eicar" in detail and len(digest) == 64
    monkeypatch.setattr(scan, "clamav", lambda d: (scan.ERROR, "ClamAV unreachable"))
    assert scan.scan(glb())[0] == scan.ERROR


@pytest.mark.django_db
def test_upload_blocked_on_failed_scan_needs_rights_and_approval_needs_clean_scan():
    u = User.objects.create_user("sup", password="x", role=Role.COMPANY_REP)
    Supplier.objects.create(owner=u, name="Acme", status="approved")
    c = APIClient()
    c.force_login(u)
    body = {"title": "Syringe", "rights_confirmed": True}
    bad = glb({"asset": {"version": "2.0"}, "buffers": [{"uri": "https://evil.example/x"}]})
    enc = lambda b: base64.b64encode(b).decode()  # noqa: E731
    r = c.post("/api/v1/my/catalogs-3d/", {**body, "asset_base64": enc(bad)}, format="json")
    assert r.status_code == 400 and "blocked" in r.json()["detail"]
    no_rights = c.post(
        "/api/v1/my/catalogs-3d/", {"title": "T", "asset_base64": enc(glb())}, format="json"
    )
    assert no_rights.status_code == 400
    r = c.post(
        "/api/v1/my/catalogs-3d/",
        {**body, "asset_base64": enc(glb()), "price_amount": "25", "price_currency": "usd"},
        format="json",
    )
    assert r.status_code == 201 and r.json()["scan"] == "clean"
    pk = r.json()["id"]
    mod = APIClient()
    mod.force_login(User.objects.create_user("mod", password="x", role=Role.MODERATOR))
    approve = {"status": "approved"}
    Catalog3D.objects.filter(pk=pk).update(scan_status="error")
    url = f"/api/v1/staff/catalogs-3d/{pk}/"
    assert mod.patch(url, approve, format="json").status_code == 400
    assert mod.post(f"{url}rescan/").json()["scan_status"] == "clean"
    assert mod.patch(url, approve, format="json").status_code == 200
    public = APIClient().get("/api/v1/catalogs-3d/").json()["results"][0]
    assert public["price"] == {"amount": "25.00", "currency": "USD"}
    lead = APIClient().post(
        "/api/v1/catalog-leads/", {"name": "A", "email": "a@b.org", "catalog": pk}, format="json"
    )
    assert lead.status_code == 201
    assert mod.get("/api/v1/staff/leads/").json()["results"][0]["catalog"] == "Syringe"
