"""The official-listing gate: nothing publishes until terms, mapping and the first batch are
approved; afterwards routine updates publish themselves, odd files are held, and clinical
records can never be reached by the factual tier."""

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.automation import datasources, publishing
from apps.automation.models import DataSource
from apps.automation.tests.test_datasources import VMD_XML, fake_fetch
from apps.clinical.models import ClinicalNote, DoseRegimen, Interaction, WithdrawalPeriod
from apps.companies.models import Company
from apps.core.models import AuditLog, PublicationTier, ReviewStatus, publication_tier
from apps.pharma.models import Generic, Product, ProductRegistration

pytestmark = pytest.mark.django_db

ALBENDAZOLE = (
    b"<CurrentAuthorisedProducts><VMDProductNo>A9</VMDProductNo><Name>Albenex</Name>"
    b"<MAHolder>Example Pharma Ltd</MAHolder><VMNo>01234/0009</VMNo>"
    b"<ActiveSubstances>Albendazole</ActiveSubstances><TargetSpecies>Sheep</TargetSpecies>"
    b"</CurrentAuthorisedProducts>"
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_user("boss", password="x", role=Role.ADMIN)


@pytest.fixture
def source(admin_user):
    call_command("seed_reference")
    s = DataSource.objects.get(slug="uk-vmd-pid")
    s.import_enabled = True
    s.save()
    datasources.confirm_terms(s, admin_user)
    return s


def run(source, monkeypatch, body=VMD_XML, etag="a"):
    fake_fetch(monkeypatch, body=body, headers={"etag": etag})
    return datasources.sync_source(source)


def approve(source, admin_user, auto=False):
    publishing.approve_mapping(source, admin_user)
    publishing.approve_first_batch(source, admin_user)
    if auto:
        source.auto_publish = True
        source.save()
    source.refresh_from_db()


def test_tiers_are_derived_from_review_status():
    assert publication_tier(ReviewStatus.OFFICIAL_REGULATORY) == PublicationTier.OFFICIAL_LISTING
    assert publication_tier(ReviewStatus.VERIFIED) == PublicationTier.CLINICALLY_REVIEWED
    assert publication_tier(ReviewStatus.EXPERT_REVIEWED) == PublicationTier.CLINICALLY_REVIEWED
    assert publication_tier(ReviewStatus.IMPORTED_UNVERIFIED) == PublicationTier.PENDING
    assert publication_tier(ReviewStatus.NEEDS_VERIFICATION) == PublicationTier.PENDING


def test_nothing_publishes_before_the_source_is_approved(source, monkeypatch):
    result = run(source, monkeypatch)
    assert result["published"]["published"] == {}
    assert not Product.objects.public().exists()
    assert not Product.objects.listed().exists()
    assert source.publication_state == "awaiting_mapping_approval"
    assert ProductRegistration.objects.exclude(data_source=source).count() == 0


def test_first_batch_needs_mapping_attribution_and_valid_records(source, monkeypatch, admin_user):
    run(source, monkeypatch)
    with pytest.raises(ValueError, match="field mapping"):
        publishing.approve_first_batch(source, admin_user)
    publishing.approve_mapping(source, admin_user)
    source.attribution_text = ""
    with pytest.raises(ValueError, match="attribution"):
        publishing.approve_first_batch(source, admin_user)


def test_first_batch_publishes_official_listings_never_clinical_review(
    source, monkeypatch, admin_user
):
    run(source, monkeypatch)
    publishing.approve_mapping(source, admin_user)
    out = publishing.approve_first_batch(source, admin_user)
    assert out["published"]["productregistration"] == 2
    for model in (Product, Generic, ProductRegistration):
        statuses = set(model.objects.public().values_list("review_status", flat=True))
        assert statuses == {ReviewStatus.OFFICIAL_REGULATORY}
    signed_off = [ReviewStatus.VERIFIED, ReviewStatus.EXPERT_REVIEWED]
    assert not Product.objects.filter(review_status__in=signed_off).exists()
    assert AuditLog.objects.filter(action="published_official_listing").count() >= 6
    source.refresh_from_db()
    assert source.first_batch_approved_at


def test_routine_update_publishes_automatically_when_enabled(source, monkeypatch, admin_user):
    run(source, monkeypatch)
    approve(source, admin_user, auto=True)
    assert source.publication_state == "auto_publishing"
    body = VMD_XML.replace(b"</VMD_PIDProducts>", ALBENDAZOLE + b"</VMD_PIDProducts>")
    result = run(source, monkeypatch, body=body, etag="b")
    assert result["published"]["published"]["productregistration"] == 1
    assert Product.objects.public().filter(brand_name="Albenex").exists()
    assert Generic.objects.public().filter(name__icontains="albendazole").exists()


def test_without_the_auto_switch_new_rows_wait(source, monkeypatch, admin_user):
    run(source, monkeypatch)
    approve(source, admin_user, auto=False)
    body = VMD_XML.replace(b"</VMD_PIDProducts>", ALBENDAZOLE + b"</VMD_PIDProducts>")
    result = run(source, monkeypatch, body=body, etag="b")
    assert result["published"]["published"] == {}
    assert not Product.objects.public().filter(brand_name="Albenex").exists()


def test_a_shrinking_file_is_held_not_applied(source, monkeypatch, admin_user):
    run(source, monkeypatch)
    approve(source, admin_user, auto=True)
    tiny = VMD_XML.split(b"<SuspendedProducts>")[0] + b"</VMD_PIDProducts>"
    with pytest.raises(datasources.SyncHeld):
        run(source, monkeypatch, body=tiny, etag="c")
    source.refresh_from_db()
    assert source.publication_state == "held_for_review"
    assert "shrank" in source.held_reason
    assert Product.objects.public().count() == 2  # existing listings untouched
    publishing.release_hold(source, admin_user)
    source.refresh_from_db()
    assert source.guard_bypass_once and not source.held_reason


def test_status_follows_the_regulator_for_official_listings(source, monkeypatch, admin_user):
    run(source, monkeypatch)
    approve(source, admin_user, auto=True)
    changed = VMD_XML.replace(b"<SuspendedProducts>", b"<CurrentAuthorisedProducts>").replace(
        b"</SuspendedProducts>", b"</CurrentAuthorisedProducts>"
    )
    run(source, monkeypatch, body=changed, etag="d")
    reg = ProductRegistration.objects.get(registration_number="01234/0002")
    assert reg.status == "registered"
    assert reg.review_status == ReviewStatus.OFFICIAL_REGULATORY


def test_a_changed_brand_for_the_same_number_is_left_for_review(source, monkeypatch, admin_user):
    run(source, monkeypatch)
    approve(source, admin_user, auto=True)
    renamed = VMD_XML.replace(b"<Name>Pausedex</Name>", b"<Name>Totally Different</Name>")
    result = run(source, monkeypatch, body=renamed, etag="e")
    assert result["inconsistent"] == 1
    product = Product.objects.get(registrations__registration_number="01234/0002")
    assert product.brand_name == "Pausedex"
    assert AuditLog.objects.filter(action="source_inconsistency").exists()


def test_factual_tier_cannot_touch_clinical_models():
    for model in (DoseRegimen, WithdrawalPeriod, ClinicalNote, Interaction):
        assert model not in publishing.FACTUAL_MODELS
    assert set(publishing.FACTUAL_MODELS) == {Generic, Product, ProductRegistration, Company}


def test_public_api_shows_provenance_and_tier(source, monkeypatch, admin_user):
    run(source, monkeypatch)
    approve(source, admin_user)
    ProductRegistration.objects.update(last_checked_at=timezone.now())
    slug = Product.objects.get(brand_name__startswith="Testcillin").slug
    data = APIClient().get(f"/api/v1/products/{slug}/").json()
    assert data["status"]["tier"] == "official_listing"
    assert data["status"]["clinically_reviewed"] is False
    prov = data["registrations"][0]["provenance"]
    assert prov["regulator"].startswith("Veterinary Medicines Directorate")
    assert prov["jurisdiction_code"] == "GB"
    assert prov["regulatory_status"] == "registered"
    assert prov["source_url"].startswith("https://www.vmd.defra.gov.uk")
    assert "Open Government Licence" in prov["attribution"]
    assert prov["clinical_review"] == "Not clinically reviewed"
    assert prov["last_checked_at"]
    assert data["listing_kind"] == "unspecified"
