"""End-to-end tests of the review pipeline: source linking, grouping, licensing, deduplication,
image processing and R2 failures, review permissions and publication restrictions.

The fixture mirrors the record shown in the admin queue: "Western University College of
Veterinary Medicine", imported from Wikipedia with a raw `source_url` and no linked Source.
"""

import hashlib

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.automation import assessment, bulk, images, pipeline, r2
from apps.automation.models import (
    BulkStatus,
    ImageAsset,
    ImageStatus,
    JobRun,
    RecordAssessment,
    SourceHealth,
)
from apps.core.models import AuditLog, ReviewStatus
from apps.core.review import set_review_status
from apps.countries.models import Country
from apps.sources import linking
from apps.sources.models import Source, SourceLink, VerificationStatus, has_source
from apps.sources.urlutil import canonicalize_url
from apps.universities.models import University

WIKI = "https://en.wikipedia.org/wiki/Western_University_College_of_Veterinary_Medicine"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
R2_ON = {
    "R2_ACCOUNT_ID": "acct",
    "R2_ACCESS_KEY_ID": "AKID",
    "R2_SECRET_ACCESS_KEY": "super-secret-value",
    "R2_BUCKET": "vetref",
    "R2_PUBLIC_BASE_URL": "https://img.example.org",
}


@pytest.fixture
def ca(db):
    return Country.objects.create(iso2="CA", slug="canada", name="Canada", currency_code="CAD")


def make_uni(country, name="Western University College of Veterinary Medicine", **kw):
    fields = {
        "city": "Pomona",
        "website": "https://www.westernu.edu/veterinary/",
        "summary": "A private veterinary college in California.",
        "source_url": WIKI,
        "source_license": "CC BY-SA 4.0 (Wikipedia)",
        "wikidata_id": "Q7988000",
        "review_status": ReviewStatus.IMPORTED_UNVERIFIED,
    }
    fields.update(kw)
    return University.objects.create(name=name, country=country, **fields)


@pytest.fixture
def western(ca):
    return make_uni(ca)


def mark_link_ok(record):
    for link in SourceLink.objects.filter(
        content_type=ContentType.objects.get_for_model(record), object_id=record.pk
    ):
        SourceHealth.objects.update_or_create(
            source=link.source,
            defaults={"checked_at": link.source.created_at, "ok": True, "status_code": 200},
        )


def client_for(role):
    user = User.objects.create_user(f"u-{role}-{User.objects.count()}", password="x", role=role)
    c = APIClient()
    c.force_login(user)
    return c, user


# ---------------------------------------------------------------- source linking


def test_root_cause_raw_url_is_not_a_linked_source(western):
    assert western.source_url and not has_source(western)
    with pytest.raises(Exception, match="source must be linked"):
        vet = User.objects.create_user("v", password="x", role=Role.VET_REVIEWER)
        set_review_status(western, ReviewStatus.VERIFIED, vet)


def test_link_record_creates_validated_sources_and_keeps_original_url(western):
    result = linking.link_record(western)
    assert result.created_sources == 2 and result.linked == 2  # Wikipedia page + Wikidata item
    assert has_source(western)
    western.refresh_from_db()
    assert western.source_url == WIKI  # original provenance untouched
    wiki = Source.objects.get(canonical_url=canonicalize_url(WIKI))
    assert wiki.provider == "wikipedia"
    assert wiki.verification_status == VerificationStatus.PROVENANCE_OK
    assert "CC BY-SA" in wiki.license_note and wiki.verified_at


def test_link_record_is_idempotent(western):
    linking.link_record(western)
    again = linking.link_record(western)
    assert again.created_sources == 0 and again.created_links == 0
    assert Source.objects.count() == 2 and SourceLink.objects.count() == 2


def test_two_records_share_one_registry_source_by_canonical_url(ca, western):
    other = make_uni(ca, "Other College", source_url=WIKI.replace("en.", "en.m.") + "?utm_source=x")
    linking.link_record(western)
    linking.link_record(other)
    assert Source.objects.filter(provider="wikipedia").count() == 1
    assert SourceLink.objects.filter(source__provider="wikipedia").count() == 2


def test_canonical_url_rules():
    c = canonicalize_url
    assert (
        c("http://www.Example.org/a/?utm_source=x&b=2&a=1#frag") == "https://example.org/a?a=1&b=2"
    )
    assert c("https://en.m.wikipedia.org/wiki/X/") == "https://en.wikipedia.org/wiki/X"
    assert c("javascript:alert(1)") == "" and c("ftp://x.org/a") == "" and c("") == ""


def test_unusable_url_is_reported_not_linked(ca):
    uni = make_uni(ca, "Bad", source_url="ftp://example.org/x", wikidata_id="")
    result = linking.link_record(uni)
    assert result.linked == 0 and result.problems


def test_unknown_publisher_stays_unverified(ca):
    uni = make_uni(ca, "Unknown", source_url="https://random-site.example/uni", wikidata_id="")
    linking.link_record(uni)
    src = Source.objects.get(provider="")
    assert src.verification_status == VerificationStatus.UNVERIFIED


def test_license_conflict_between_entries_is_flagged_not_merged(western):
    a = Source.objects.create(
        source_type="other", title="A", url=WIKI, license_note="CC BY-SA 4.0 (Wikipedia)"
    )
    b = Source.objects.create(
        source_type="other", title="B", url=WIKI + "/", license_note="All rights reserved"
    )
    assert a.canonical_url == b.canonical_url
    out = linking.dedupe_sources()
    assert out == {"merged": 0, "conflicts": 1}
    a.refresh_from_db(), b.refresh_from_db()
    assert a.verification_status == b.verification_status == VerificationStatus.CONFLICT


def test_dedupe_merges_exact_duplicates_and_repoints_links(western):
    a = Source.objects.create(source_type="other", title="A", url=WIKI)
    b = Source.objects.create(
        source_type="other", title="B", url=WIKI + "#history", license_note="CC BY-SA 4.0"
    )
    ct = ContentType.objects.get_for_model(western)
    SourceLink.objects.create(source=b, content_type=ct, object_id=western.pk)
    out = linking.dedupe_sources()
    assert out["merged"] == 1
    assert Source.objects.filter(canonical_url=a.canonical_url).count() == 1
    assert SourceLink.objects.get(object_id=western.pk).source_id == a.pk
    a.refresh_from_db()
    assert a.license_note == "CC BY-SA 4.0"  # blanks filled from the duplicate
    assert AuditLog.objects.filter(action="source_merged").count() == 1


def test_invalid_source_cannot_support_publication(western):
    linking.link_record(western)
    Source.objects.update(verification_status=VerificationStatus.INVALID)
    vet = User.objects.create_user("v2", password="x", role=Role.VET_REVIEWER)
    with pytest.raises(Exception, match="source must be linked"):
        set_review_status(western, ReviewStatus.VERIFIED, vet)


# ---------------------------------------------------------------- assessment and grouping


def test_assessment_groups_and_flags_before_linking(western):
    a = assessment.assess(western)
    assert a.source_state == "raw_url_only" and "raw_url_only" in a.issues
    assert a.recommendation == "fix_source"
    assert (a.model_key, a.country_iso2, a.provider, a.batch) == (
        "universities.university",
        "CA",
        "wikipedia",
        western.created_at.date().isoformat(),
    )
    assert a.completeness == 100 and a.missing_fields == []


def test_complete_verified_checked_record_is_safe_batch_eligible(western):
    pipeline.prepare(western)
    mark_link_ok(western)
    a = assessment.assess(western)
    assert a.source_state == "linked_ok" and a.trust_level == "high"
    assert a.recommendation == "safe_batch"


def test_unchecked_link_is_not_eligible(western):
    pipeline.prepare(western)  # linked and verified, but never probed
    assert assessment.assess(western).recommendation == "review"


def test_incomplete_record_is_not_eligible(ca):
    uni = make_uni(ca, "Sparse", website="", summary="", city="")
    pipeline.prepare(uni)
    mark_link_ok(uni)
    a = assessment.assess(uni)
    assert a.recommendation == "incomplete" and "Website" in a.missing_fields


def test_duplicate_candidates_are_detected_and_block_safe_approval(ca, western):
    twin = make_uni(ca, "Western University College of Veterinary Medicne", wikidata_id="Q7988000")
    for rec in (western, twin):
        pipeline.prepare(rec)
        mark_link_ok(rec)
    a = assessment.assess(western)
    assert "duplicate_candidate" in a.issues and a.duplicates
    assert a.recommendation == "duplicate"


def test_development_and_suspicious_records_are_blocked(ca):
    dev = make_uni(ca, "Dev U", is_development_data=True)
    scam = make_uni(ca, "Pay a fee U", summary="Send money via western union to enrol")
    assert assessment.assess(dev).recommendation == "blocked"
    assert assessment.assess(scam).recommendation == "blocked"


def test_clinical_and_regulator_models_never_become_safe_batch(db):
    from apps.pharma.models import Generic

    g = Generic.objects.create(name="Amoxicillin", review_status=ReviewStatus.IMPORTED_UNVERIFIED)
    a = assessment.assess(g)
    assert a.risk == "high" and a.recommendation in ("clinical_review", "regulator_review")
    assert a.recommendation != "safe_batch"


def test_change_detection_between_imports(western):
    assessment.assess(western)
    western.summary = "A new description from the next import."
    western.save()
    a = assessment.assess(western)
    assert a.changed_fields == ["summary"] and "changed_since_import" in a.issues


def test_assessment_is_idempotent(western):
    assessment.assess(western)
    assessment.assess(western)
    assert RecordAssessment.objects.count() == 1


# ---------------------------------------------------------------- images and R2


def licensed_uni(country, **kw):
    return make_uni(
        country,
        image_url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Logo.png/640px-Logo.png",
        image_page_url="https://commons.wikimedia.org/wiki/File:Logo.png",
        image_credit="Jane Photographer",
        image_license="CC BY-SA 4.0",
        image_license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        **kw,
    )


def ok_fetcher(url):
    return 200, PNG, {"content-type": "image/png"}


class FakeR2:
    def __init__(self, status=200):
        self.status, self.calls = status, []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        return self.status, b""


def test_non_open_licence_is_recorded_but_never_downloaded(ca):
    uni = make_uni(
        ca, image_url="https://example.org/logo.png", image_license="All rights reserved"
    )
    (asset,) = images.discover(uni)
    assert asset.status == ImageStatus.REJECTED and "redistribution" in asset.status_detail


def test_cc_by_without_credit_is_rejected(ca):
    uni = make_uni(
        ca, image_url="https://example.org/a.png", image_license="CC BY 4.0", image_credit=""
    )
    (asset,) = images.discover(uni)
    assert asset.status == ImageStatus.REJECTED and "attribution" in asset.status_detail


def test_http_image_url_rejected(ca):
    uni = make_uni(ca, image_url="http://example.org/a.png", image_license="CC0")
    assert images.discover(uni)[0].status == ImageStatus.REJECTED


@override_settings(**R2_ON)
def test_eligible_image_is_stored_with_attribution_metadata(ca):
    uni = licensed_uni(ca)
    (asset,) = images.discover(uni)
    fake = FakeR2()
    out = images.process(asset, fetcher=ok_fetcher, transport=fake)
    digest = hashlib.sha256(PNG).hexdigest()
    assert out.status == ImageStatus.STORED and out.sha256 == digest
    assert out.object_key == f"images/{digest[:2]}/{digest}.png"
    (method, url, headers, body) = fake.calls[0]
    assert method == "PUT" and url.startswith(
        "https://acct.r2.cloudflarestorage.com/vetref/images/"
    )
    assert body == PNG
    assert "Jane%20Photographer" in headers["x-amz-meta-credit"]
    assert headers["x-amz-meta-license"] == "CC%20BY-SA%204.0"
    assert "commons.wikimedia.org" in headers["x-amz-meta-attribution-url"].replace(
        "%3A", ":"
    ).replace("%2F", "/")
    assert "super-secret-value" not in str(headers)  # the secret never travels, only a signature
    assert images.display_url(out).startswith("https://img.example.org/images/")


@override_settings(**R2_ON)
def test_identical_bytes_are_stored_once(ca):
    a = licensed_uni(ca)
    b = make_uni(
        ca,
        "Second U",
        image_url="https://upload.wikimedia.org/other.png",
        image_page_url="https://commons.wikimedia.org/wiki/File:Other.png",
        image_credit="Someone",
        image_license="CC BY 4.0",
        source_url="https://en.wikipedia.org/wiki/Second",
    )
    fake = FakeR2()
    first = images.process(images.discover(a)[0], fetcher=ok_fetcher, transport=fake)
    second = images.process(images.discover(b)[0], fetcher=ok_fetcher, transport=fake)
    assert len(fake.calls) == 1  # one upload for two references
    assert second.duplicate_of_id == first.pk and second.object_key == first.object_key


@override_settings(**R2_ON)
@pytest.mark.parametrize(
    ("fetcher", "needle"),
    [
        (lambda u: (404, b"", {}), "HTTP 404"),
        (
            lambda u: (200, b"<svg onload=alert(1)>", {"content-type": "image/svg+xml"}),
            "allowed image",
        ),
        (lambda u: (200, b"%PDF-1.4", {"content-type": "image/png"}), "allowed image"),
        (lambda u: (200, b"", {}), "empty"),
        (lambda u: (200, PNG, {"content-type": "image/jpeg"}), "does not match"),
    ],
)
def test_bad_downloads_fail_visibly_and_can_retry(ca, fetcher, needle):
    (asset,) = images.discover(licensed_uni(ca))
    out = images.process(asset, fetcher=fetcher, transport=FakeR2())
    assert out.status == ImageStatus.FAILED and needle in out.status_detail and out.attempts == 1


@override_settings(**R2_ON)
def test_r2_outage_marks_failed_then_manual_retry_succeeds(ca):
    (asset,) = images.discover(licensed_uni(ca))
    out = images.process(asset, fetcher=ok_fetcher, transport=FakeR2(status=503))
    assert out.status == ImageStatus.FAILED and "HTTP 503" in out.status_detail
    assert not out.object_key
    again = images.retry(out, fetcher=ok_fetcher, transport=FakeR2(status=200))
    assert again.status == ImageStatus.STORED and again.attempts == 0  # reset, then stored


@override_settings(**R2_ON)
def test_r2_unreachable_is_recorded(ca):
    def boom(*a):
        raise OSError("down")

    (asset,) = images.discover(licensed_uni(ca))
    out = images.process(asset, fetcher=ok_fetcher, transport=boom)
    assert out.status == ImageStatus.FAILED and "unreachable" in out.status_detail


@override_settings(R2_ACCOUNT_ID="", R2_ACCESS_KEY_ID="", R2_SECRET_ACCESS_KEY="", R2_BUCKET="")
def test_without_r2_config_nothing_is_fetched_or_uploaded(ca):
    (asset,) = images.discover(licensed_uni(ca))

    def must_not_fetch(url):
        raise AssertionError("downloaded without R2 configured")

    out = images.process(asset, fetcher=must_not_fetch)
    assert out.status == ImageStatus.PENDING and "not configured" in out.status_detail
    assert not r2.configured()


@override_settings(**R2_ON)
def test_retry_limit_stops_automatic_reprocessing(ca):
    (asset,) = images.discover(licensed_uni(ca))
    asset.status, asset.attempts = ImageStatus.FAILED, images.MAX_ATTEMPTS
    asset.save()
    assert images.process_pending(fetcher=ok_fetcher, transport=FakeR2()) == {
        "stored": 0,
        "failed": 0,
        "r2_configured": True,
    }


def test_changed_image_supersedes_old_asset(ca):
    uni = licensed_uni(ca)
    images.discover(uni)
    uni.image_url = "https://upload.wikimedia.org/new.png"
    uni.save()
    images.discover(uni)
    states = sorted(ImageAsset.objects.values_list("status", flat=True))
    assert states == [ImageStatus.PENDING, ImageStatus.SUPERSEDED]


def test_sigv4_signature_matches_aws_documented_vector():
    h = r2.sign_headers(
        method="GET",
        host="examplebucket.s3.amazonaws.com",
        path="/test.txt",
        headers={"range": "bytes=0-9"},
        payload_sha256=hashlib.sha256(b"").hexdigest(),
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        amz_date="20130524T000000Z",
        region="us-east-1",
    )
    assert h["Authorization"].endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


# ---------------------------------------------------------------- pipeline and bulk


def test_pipeline_flows_a_new_import_to_a_recommendation(ca, western):
    first = pipeline.run_review_pipeline(limit=50, budget_seconds=60)
    assert first["records"] == 1 and first["assessed"] == 1 and first["links_created"] == 2
    a = RecordAssessment.objects.get()
    assert a.source_state == "linked_ok"
    # A second run finds nothing stale: idempotent.
    second = pipeline.run_review_pipeline(limit=50, budget_seconds=60)
    assert second["records"] == 0 and Source.objects.count() == 2


def test_review_pipeline_task_is_registered_and_logged(western):
    from apps.automation.tasks import run_task

    run = run_task("review-pipeline")
    assert run.status == "ok" and run.summary["assessed"] == 1
    assert JobRun.objects.filter(task="review-pipeline").count() == 1


def test_bulk_link_sources_preview_then_execute(ca, western):
    other = make_uni(ca, "Another College", source_url="https://en.wikipedia.org/wiki/Another")
    admin = User.objects.create_user("adm", password="x", role=Role.ADMIN)
    targets = [("universities.university", western.pk), ("universities.university", other.pk)]
    plan = bulk.preview("link_sources", targets, admin)
    assert plan["eligible"] == 2 and not has_source(western)  # preview changed nothing
    op = bulk.start("link_sources", plan["targets"], admin, "backfill")
    while op.status == BulkStatus.RUNNING:
        op = bulk.step(op, chunk=1)
    assert (op.succeeded, op.failed, op.status) == (2, 0, BulkStatus.DONE)
    assert has_source(western) and has_source(other)
    assert AuditLog.objects.filter(action="bulk_link_sources").count() == 2


def test_bulk_approval_only_touches_safe_records_and_needs_a_signer(ca, western):
    risky = make_uni(
        ca,
        "Risky",
        source_url="https://unknown.example/r",
        wikidata_id="",
        website="https://risky.example/",
    )
    for rec in (western, risky):
        pipeline.prepare(rec)
        mark_link_ok(rec)
    targets = [("universities.university", western.pk), ("universities.university", risky.pk)]
    editor = User.objects.create_user("ed", password="x", role=Role.EDITOR)
    assert bulk.preview("approve_safe", targets, editor)["eligible"] == 0  # role cannot sign off
    vet = User.objects.create_user("vet", password="x", role=Role.VET_REVIEWER)
    plan = bulk.preview("approve_safe", targets, vet)
    assert plan["eligible"] == 1 and plan["skipped"] == 1
    op = bulk.start("approve_safe", plan["targets"], vet, "Checked sample")
    op = bulk.step(op)
    western.refresh_from_db(), risky.refresh_from_db()
    assert western.review_status == ReviewStatus.VERIFIED and western.reviewed_by == vet
    assert risky.review_status == ReviewStatus.IMPORTED_UNVERIFIED
    assert AuditLog.objects.filter(action="review_status_changed").count() == 1


def test_bulk_rechecks_eligibility_at_execution_time(ca, western):
    pipeline.prepare(western)
    mark_link_ok(western)
    vet = User.objects.create_user("vet2", password="x", role=Role.VET_REVIEWER)
    plan = bulk.preview("approve_safe", [("universities.university", western.pk)], vet)
    assert plan["eligible"] == 1
    op = bulk.start("approve_safe", plan["targets"], vet, "x")
    western.is_development_data = True  # becomes ineligible between preview and execution
    western.save()
    op = bulk.step(op)
    western.refresh_from_db()
    assert op.skipped == 1 and western.review_status == ReviewStatus.IMPORTED_UNVERIFIED


def test_bulk_never_approves_high_risk_models(db):
    from apps.pharma.models import Generic

    g = Generic.objects.create(name="Ivermectin", review_status=ReviewStatus.IMPORTED_UNVERIFIED)
    vet = User.objects.create_user("vet3", password="x", role=Role.ADMIN)
    plan = bulk.preview("approve_safe", [("pharma.generic", g.pk)], vet)
    assert plan["eligible"] == 0


@override_settings(R2_ACCOUNT_ID="", R2_ACCESS_KEY_ID="", R2_SECRET_ACCESS_KEY="", R2_BUCKET="")
def test_bulk_images_skipped_when_r2_missing(ca):
    uni = licensed_uni(ca)
    admin = User.objects.create_user("adm2", password="x", role=Role.ADMIN)
    plan = bulk.preview("process_images", [("universities.university", uni.pk)], admin)
    assert plan["eligible"] == 0 and "R2" in next(iter(plan["skipped_reasons"]))


@override_settings(**R2_ON)
def test_bulk_failed_records_can_be_retried(ca, monkeypatch):
    uni = licensed_uni(ca)
    admin = User.objects.create_user("adm3", password="x", role=Role.ADMIN)
    monkeypatch.setattr(images, "_default_fetcher", lambda url: (500, b"", {}))
    plan = bulk.preview("process_images", [("universities.university", uni.pk)], admin)
    op = bulk.step(bulk.start("process_images", plan["targets"], admin, ""))
    assert op.failed == 1 and op.status == BulkStatus.PARTIAL
    monkeypatch.setattr(images, "_default_fetcher", ok_fetcher)
    monkeypatch.setattr(r2, "_urllib_transport", FakeR2())
    retry = bulk.step(bulk.retry_failed(op, admin))
    assert retry.succeeded == 1 and retry.retry_of_id == op.pk


# ---------------------------------------------------------------- API and permissions


def test_pipeline_endpoints_require_staff(western):
    for url in ("overview", "groups", "items", "search", "facets"):
        assert APIClient().get(f"/api/v1/staff/pipeline/{url}/").status_code in (401, 403)
    student, _ = client_for(Role.STUDENT)
    assert student.get("/api/v1/staff/pipeline/overview/").status_code == 403
    assert (
        student.post("/api/v1/staff/pipeline/bulk/preview/", {}, format="json").status_code == 403
    )


def test_grouping_filtering_and_search_api(ca, western):
    make_uni(ca, "Elsewhere Vet School", source_url="https://en.wikipedia.org/wiki/E")
    pipeline.run_review_pipeline(limit=50, budget_seconds=60)
    c, _ = client_for(Role.EDITOR)
    by_type = c.get("/api/v1/staff/pipeline/groups/?by=type").json()["groups"]
    assert by_type == [{"key": "universities.university", "label": "Universities", "count": 2}]
    by_country = c.get("/api/v1/staff/pipeline/groups/?by=country").json()["groups"]
    assert by_country[0]["label"] == "Canada" and by_country[0]["count"] == 2
    assert c.get("/api/v1/staff/pipeline/groups/?by=nope").status_code == 400
    items = c.get("/api/v1/staff/pipeline/items/?country=CA&q=western").json()
    assert items["count"] == 1 and items["results"][0]["label"].startswith("Western University")
    assert items["results"][0]["has_source"] is True
    by_id = c.get(f"/api/v1/staff/pipeline/search/?q={western.pk}").json()
    assert any(r["id"] == western.pk for r in by_id["results"])
    by_key = c.get(f"/api/v1/staff/pipeline/search/?q=universities.university:{western.pk}").json()
    assert by_key["count"] == 1
    by_source = c.get("/api/v1/staff/pipeline/search/?q=wikidata Q7988000").json()
    assert by_source["count"] >= 1
    by_issue = c.get("/api/v1/staff/pipeline/groups/?by=issue").json()["groups"]
    assert isinstance(by_issue, list)


def test_overview_counts_and_r2_status(ca, western):
    pipeline.run_review_pipeline(limit=50, budget_seconds=60)
    c, _ = client_for(Role.EDITOR)
    o = c.get("/api/v1/staff/pipeline/overview/").json()
    assert o["awaiting_review"] == 1 and o["total_imported"] == 1
    assert o["r2"]["configured"] is False and o["source_problems"] == 0
    assert set(o["images"]) == {"stored", "pending", "failed", "rejected"}


def test_record_detail_shows_linked_source_for_the_western_record(ca, western):
    c, _ = client_for(Role.EDITOR)
    url = f"/api/v1/staff/review-queue/universities.university/{western.pk}/"
    before = c.get(url).json()
    assert before["sources"] == [] and before["raw_source_url"] == WIKI  # the reported bug
    assert before["has_source"] is False
    repaired = c.post(f"/api/v1/staff/records/universities.university/{western.pk}/repair/").json()
    assert repaired["created_sources"] == 2
    after = c.get(url).json()
    assert after["has_source"] is True
    wiki = next(s for s in after["sources"] if s["provider"] == "wikipedia")
    assert wiki["url"] == WIKI and wiki["verification_status"] == "provenance_ok"
    assert "CC BY-SA" in wiki["license_note"]
    assert after["assessment"]["source_state"] == "linked_ok"
    assert any(e["action"] == "record repaired" for e in after["audit"])
    assert after["timeline"]["imported_at"] and after["sections"][0]["title"] == "Institution"


def test_bulk_api_preview_start_step_and_permissions(ca, western):
    pipeline.prepare(western)
    mark_link_ok(western)
    assessment.assess(western)
    ed, _ = client_for(Role.EDITOR)
    body = {"action": "approve_safe", "filter": {"model": "universities.university"}}
    preview = ed.post("/api/v1/staff/pipeline/bulk/preview/", body, format="json").json()
    assert preview["selected"] == 1 and preview["eligible"] == 0  # editors cannot sign off
    r = ed.post(
        "/api/v1/staff/pipeline/bulk/start/",
        {**body, "expected_count": 1, "reason": "x"},
        format="json",
    )
    assert r.status_code == 403
    vet, _ = client_for(Role.VET_REVIEWER)
    preview = vet.post("/api/v1/staff/pipeline/bulk/preview/", body, format="json").json()
    assert preview["eligible"] == 1
    stale = vet.post(
        "/api/v1/staff/pipeline/bulk/start/",
        {**body, "expected_count": 5, "reason": "x"},
        format="json",
    )
    assert stale.status_code == 409
    no_reason = vet.post(
        "/api/v1/staff/pipeline/bulk/start/", {**body, "expected_count": 1}, format="json"
    )
    assert no_reason.status_code == 400
    start = vet.post(
        "/api/v1/staff/pipeline/bulk/start/",
        {**body, "expected_count": 1, "reason": "Verified sample of 5"},
        format="json",
    )
    assert start.status_code == 201
    op_id = start.json()["id"]
    done = vet.post(f"/api/v1/staff/pipeline/bulk/{op_id}/step/").json()
    assert done["status"] == "done" and done["succeeded"] == 1
    western.refresh_from_db()
    assert western.review_status == ReviewStatus.VERIFIED
    other, _ = client_for(Role.EDITOR)
    assert other.post(f"/api/v1/staff/pipeline/bulk/{op_id}/step/").status_code == 403
