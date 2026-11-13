from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.content.models import Article, ArticleStatus

BODY = "Paragraph about learning veterinary pharmacology. " * 8


def api(role, name=None):
    u, _ = User.objects.get_or_create(username=name or f"u-{role}", defaults={"role": role})
    c = APIClient()
    c.force_login(u)
    return c, u


@pytest.mark.django_db
def test_submission_is_hidden_until_an_editor_publishes_and_html_is_stripped():
    c, _ = api(Role.STUDENT)
    r = c.post(
        "/api/v1/articles/submit/",
        {"title": "<b>Study tips</b>", "body": "<script>alert(1)</script>" + BODY},
        format="json",
    )
    assert r.status_code == 201, r.content
    a = Article.objects.get()
    assert "<" not in a.body and "<" not in a.title and a.status == ArticleStatus.REVIEW
    assert APIClient().get("/api/v1/articles/").json()["results"] == []
    assert APIClient().get(f"/api/v1/articles/{a.slug}/").status_code == 404
    ed, _ = api(Role.EDITOR)
    assert ed.post(f"/api/v1/staff/articles/{a.pk}/publish/").status_code == 200
    assert len(APIClient().get("/api/v1/articles/").json()["results"]) == 1
    detail = APIClient().get(f"/api/v1/articles/{a.slug}/").json()
    assert detail["title"] == "Study tips"


@pytest.mark.django_db
def test_students_cannot_use_staff_endpoints_or_publish():
    c, _ = api(Role.STUDENT)
    assert c.get("/api/v1/staff/articles/").status_code == 403
    assert c.post("/api/v1/staff/articles/1/publish/").status_code == 403


@pytest.mark.django_db
def test_clinical_articles_need_a_vet_reviewer_and_references():
    c, _ = api(Role.STUDENT)
    c.post(
        "/api/v1/articles/submit/",
        {"title": "Dosage guide", "body": "The dose of this antibiotic is... " + BODY},
        format="json",
    )
    a = Article.objects.get()
    assert a.medical
    ed, _ = api(Role.EDITOR)
    assert ed.post(f"/api/v1/staff/articles/{a.pk}/publish/").status_code == 403
    vet, _ = api(Role.VET_REVIEWER)
    assert vet.post(f"/api/v1/staff/articles/{a.pk}/publish/").status_code == 409  # no references
    a.references = "https://example.org/guideline"
    a.save()
    assert vet.post(f"/api/v1/staff/articles/{a.pk}/publish/").status_code == 200


@pytest.mark.django_db
def test_scheduled_articles_go_public_only_when_due_and_edits_pull_them_back():
    ed, user = api(Role.EDITOR)
    r = ed.post(
        "/api/v1/staff/articles/",
        {
            "title": "Scheduled piece",
            "body": BODY,
            "publish_at": (timezone.now() + timedelta(days=1)).isoformat(),
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    pk = r.json()["id"]
    assert ed.post(f"/api/v1/staff/articles/{pk}/schedule/").status_code == 200
    assert APIClient().get("/api/v1/articles/").json()["results"] == []
    Article.objects.filter(pk=pk).update(publish_at=timezone.now() - timedelta(minutes=1))
    assert len(APIClient().get("/api/v1/articles/").json()["results"]) == 1
    ed.patch(f"/api/v1/staff/articles/{pk}/", {"body": BODY + " edited"}, format="json")
    assert Article.objects.get(pk=pk).status == ArticleStatus.REVIEW
    assert APIClient().get("/api/v1/articles/").json()["results"] == []
    assert Article.objects.get(pk=pk).revisions.count() == 2


@pytest.mark.django_db
def test_rejects_non_https_references_and_canonical():
    ed, _ = api(Role.EDITOR)
    bad = ed.post(
        "/api/v1/staff/articles/",
        {"title": "T", "body": BODY, "references": "javascript:alert(1)"},
        format="json",
    )
    assert bad.status_code == 400
    bad = ed.post(
        "/api/v1/staff/articles/",
        {"title": "T", "body": BODY, "canonical_url": "http://x.org"},
        format="json",
    )
    assert bad.status_code == 400


@pytest.mark.django_db
def test_topic_suggestions_label_their_basis_and_ai_draft_needs_a_route():
    from apps.species.models import Species

    Species.objects.create(slug="cat", name="Cat")
    ed, _ = api(Role.EDITOR)
    r = ed.post("/api/v1/staff/articles/suggest-topics/")
    assert r.status_code == 201
    assert "AI suggestions skipped" in r.json()["note"]
    topics = ed.get("/api/v1/staff/topics/").json()["results"]
    assert topics and all(
        t["basis"] == "catalogue_gap" for t in topics
    )  # never claimed as trend data
    r = ed.post(f"/api/v1/staff/topics/{topics[0]['id']}/draft/")
    assert r.status_code == 409
    again = ed.post("/api/v1/staff/articles/suggest-topics/").json()
    assert again["created"] == 0  # no duplicates
