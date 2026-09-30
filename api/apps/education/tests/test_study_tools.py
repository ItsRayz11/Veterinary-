from datetime import UTC, date, datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.core.review import set_review_status
from apps.education import study_tools
from apps.education.models import (
    BookReference,
    ExamAnswer,
    ExamAttempt,
    Flashcard,
    FlashcardProgress,
    Lesson,
    Option,
    Question,
    Subject,
    Topic,
)
from apps.sources.models import Source, SourceLink

TODAY = date(2026, 6, 1)


@pytest.fixture
def topic(db):
    subject = Subject.objects.create(name="Pharmacology")
    return Topic.objects.create(subject=subject, name="Antibacterials")


@pytest.fixture
def student(db):
    return User.objects.create_user("stu", password="x", role=Role.STUDENT)


def make_card(topic, front="Front?", published=True):
    card = Flashcard.objects.create(topic=topic, front=front, back="Back.")
    if published:
        Flashcard.objects.filter(pk=card.pk).update(review_status="manufacturer_supplied")
        card.refresh_from_db()
    return card


def test_leitner_correct_moves_up_and_wrong_resets(topic, student):
    card = make_card(topic)
    expected = [(2, date(2026, 6, 3)), (3, date(2026, 6, 5)), (4, date(2026, 6, 9))]
    for box, due in expected:
        p = study_tools.record_review(student, card, True, TODAY)
        assert (p.box, p.due_on) == (box, due)
    p = study_tools.record_review(student, card, False, TODAY)
    assert (p.box, p.due_on) == (1, date(2026, 6, 2))
    for _ in range(8):
        p = study_tools.record_review(student, card, True, TODAY)
    assert p.box == 5 and p.due_on == date(2026, 6, 17)  # capped at box 5 (16 days)
    assert (p.times_correct, p.times_wrong) == (11, 1)


def test_due_cards_lists_due_then_new_and_skips_unpublished_and_future(topic, student):
    a, b, c = make_card(topic, "A"), make_card(topic, "B"), make_card(topic, "C")
    make_card(topic, "hidden", published=False)
    study_tools.record_review(student, a, True, TODAY)  # due 2026-06-03
    study_tools.record_review(student, b, False, date(2026, 5, 1))  # due 2026-05-02: overdue
    fronts = [x.front for x in study_tools.due_cards(student, TODAY)]
    assert fronts == ["B", "C"]  # overdue first, then unseen; A not due yet; hidden excluded
    assert [x.front for x in study_tools.due_cards(student, date(2026, 6, 3))] == ["B", "A", "C"]
    assert FlashcardProgress.objects.filter(card=c).count() == 0  # listing never creates rows


def test_flashcard_api_permissions_and_validation(topic, student):
    card = make_card(topic)
    hidden = make_card(topic, "h", published=False)
    anon = APIClient()
    assert [c["front"] for c in anon.get("/api/v1/study/flashcards/").json()] == ["Front?"]
    assert anon.get("/api/v1/study/flashcards/due/").status_code in (401, 403)
    c = APIClient()
    c.force_login(student)
    assert (
        c.post(
            f"/api/v1/study/flashcards/{hidden.pk}/review/", {"correct": True}, format="json"
        ).status_code
        == 404
    )
    assert (
        c.post(
            f"/api/v1/study/flashcards/{card.pk}/review/", {"correct": "yes"}, format="json"
        ).status_code
        == 400
    )
    r = c.post(f"/api/v1/study/flashcards/{card.pk}/review/", {"correct": True}, format="json")
    assert r.status_code == 200 and r.json()["box"] == 2
    assert len(c.get("/api/v1/study/flashcards/due/").json()) == 0  # reviewed, next due later


def test_flashcards_and_lessons_need_source_and_reviewer_to_go_public(topic, student):
    card = Flashcard.objects.create(topic=topic, front="F", back="B")
    reviewer = User.objects.create_user("vet", password="x", role=Role.VET_REVIEWER)
    with pytest.raises(Exception, match="source"):
        set_review_status(card, "verified", reviewer)
    src = Source.objects.create(source_type="other", title="Book", url="https://e.org")
    SourceLink.objects.create(source=src, target=card)
    with pytest.raises(Exception, match="veterinarian"):
        set_review_status(card, "verified", student)
    set_review_status(card, "verified", reviewer)
    assert Flashcard.objects.public().filter(pk=card.pk).exists()


def test_lessons_and_books_public_api(topic):
    lesson = Lesson.objects.create(topic=topic, title="Beta-lactams", body="Para one.\n\nPara two.")
    hidden = Lesson.objects.create(topic=topic, title="Draft", body="x")
    Lesson.objects.filter(pk=lesson.pk).update(review_status="manufacturer_supplied")
    api = APIClient()
    assert [x["slug"] for x in api.get("/api/v1/study/lessons/").json()] == ["beta-lactams"]
    assert api.get(f"/api/v1/study/lessons/{hidden.slug}/").status_code == 404
    detail = api.get("/api/v1/study/lessons/beta-lactams/").json()
    assert detail["body"].startswith("Para one") and detail["sources"] == []
    BookReference.objects.create(title="Shown", is_published=True)
    BookReference.objects.create(title="Hidden")
    assert [b["title"] for b in api.get("/api/v1/study/books/").json()] == ["Shown"]


def test_progress_summary_history_subject_and_weak_topics(topic, student):
    q = [Question.objects.create(topic=topic, stem=f"Q{i}") for i in range(4)]
    opts = {
        x.pk: (
            Option.objects.create(question=x, label="A", text="a", is_correct=True),
            Option.objects.create(question=x, label="B", text="b"),
        )
        for x in q
    }
    attempt = ExamAttempt.objects.create(
        user=student, submitted_at=datetime(2026, 6, 1, tzinfo=UTC), score=1
    )
    for i, question in enumerate(q):
        right, wrong = opts[question.pk]
        ExamAnswer.objects.create(
            attempt=attempt,
            question=question,
            selected=right if i == 0 else wrong,
            is_correct=(i == 0),
        )
    # someone else's exam must not leak in
    other = User.objects.create_user("o", password="x")
    ExamAttempt.objects.create(user=other, submitted_at=datetime(2026, 6, 2, tzinfo=UTC), score=0)
    s = study_tools.progress_summary(student)
    assert [(h["score"], h["total"], h["percent"]) for h in s["history"]] == [(1, 4, 25)]
    assert s["subjects"] == [{"subject": "Pharmacology", "correct": 1, "total": 4, "percent": 25}]
    assert s["weak_topics"][0]["topic"] == "Antibacterials"
    c = APIClient()
    assert c.get("/api/v1/study/progress/").status_code in (401, 403)
    c.force_login(student)
    assert c.get("/api/v1/study/progress/").json()["history"][0]["percent"] == 25
