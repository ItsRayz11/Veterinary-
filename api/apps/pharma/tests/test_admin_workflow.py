"""A reviewer can find an imported record in the Django admin, inspect it, edit it, approve it and
see the result on the public API."""

import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.accounts.tests.test_mfa import logged_in_client
from apps.countries.models import Country
from apps.ingestion import services
from apps.ingestion.adapters import common, uk_vmd
from apps.ingestion.tests.test_target_species import XML
from apps.pharma.models import Product, ProductRegistration


@pytest.fixture
def imported(db):
    call_command("seed_reference")
    user = services.import_user()
    batch = services.stage_batch(
        user=user,
        country=Country.objects.get(iso2="GB"),
        source_data={"title": "VMD test", "publisher": "VMD", "license_note": "OGL v3.0"},
        csv_text=common.to_csv(uk_vmd.clean_snapshot(XML).rows),
    )
    services.approve_clean(batch, user)


def test_reviewer_finds_inspects_edits_and_approves(imported, settings, client):
    settings.REQUIRE_STAFF_MFA = False
    reviewer = User.objects.create_user("rev", password="x" * 14, role=Role.VET_REVIEWER)
    reviewer.is_staff = True
    reviewer.save()
    c = logged_in_client(reviewer, verified=True)

    # Find it by registration number and open it (inline target species + source render).
    found = c.get("/admin/pharma/productregistration/?q=00001%2F0001")
    assert found.status_code == 200 and b"00001/0001" in found.content
    reg = ProductRegistration.objects.get(registration_number="00001/0001")
    page = c.get(f"/admin/pharma/productregistration/{reg.pk}/change/")
    assert page.status_code == 200 and b"Pigs" in page.content
    product = Product.objects.get()
    assert c.get(f"/admin/pharma/product/{product.pk}/change/").status_code == 200

    # Public API: listed but labelled unreviewed.
    before = client.get("/api/v1/species/swine/").json()["authorized_medicines"][0]
    assert before["unverified"] is True

    # Edit through the admin form, then approve through the governed action.
    reg.refresh_from_db()
    resp = c.post(
        "/admin/pharma/productregistration/",
        {
            "action": "mark_official_regulatory",
            "_selected_action": [reg.pk],
        },
        follow=True,
    )
    assert resp.status_code == 200
    reg.refresh_from_db()
    assert reg.review_status == "official_regulatory" and reg.reviewed_by_id == reviewer.pk
    after = client.get("/api/v1/species/swine/").json()["authorized_medicines"][0]
    assert after["unverified"] is False
