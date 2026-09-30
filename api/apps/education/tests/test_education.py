import random

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.core import review
from apps.core.models import ReviewStatus
from apps.education import services
from apps.education.models import Option, Question, Subject, Topic
from apps.sources.models import Source


@pytest.fixture
def bank(db):
    subj = Subject.objects.create(name="Pharmacology")
    t1 = Topic.objects.create(subject=subj, name="Antibacterials")
    t2 = Topic.objects.create(subject=subj, name="Anaesthetics")
    src = Source.objects.create(source_type="other", title="Own item", publisher="Team")
    qs = []
    for i in range(25):
        q = Question.objects.create(
            topic=t1 if i % 2 else t2,
            stem=f"Placeholder question {i}?",
            source=src,
            review_status=ReviewStatus.EXPERT_REVIEWED,
            university="UVAS",
            year=2024,
        )
        for label, correct in (("A", True), ("B", False), ("C", False), ("D", False)):
            Option.objects.create(question=q, label=label, text=f"opt {label}", is_correct=correct)
        qs.append(q)
    return qs


@pytest.fixture
def student(db):
    return User.objects.create_user("stu", password="x", role=Role.STUDENT)


def test_only_one_correct_option_per_question(bank):
    with pytest.raises(IntegrityError), transaction.atomic():
        Option.objects.create(question=bank[0], label="E", text="x", is_correct=True)


def test_cannot_publish_question_without_single_correct_option(db):
    t = Topic.objects.create(subject=Subject.objects.create(name="S"), name="T")
    src = Source.objects.create(source_type="other", title="s", publisher="p")
    q = Question.objects.create(topic=t, stem="Q?", source=src)
    Option.objects.create(question=q, label="A", text="a")
    Option.objects.create(question=q, label="B", text="b")
    vet = User.objects.create_user("vet", password="x", role=Role.VET_REVIEWER)
    with pytest.raises(ValidationError):
        review.set_review_status(q, ReviewStatus.VERIFIED, vet)
    Option.objects.filter(question=q, label="A").update(is_correct=True)
    review.set_review_status(q, ReviewStatus.VERIFIED, vet)
    assert Question.objects.public().count() == 1


def test_exam_size_and_availability_validated(bank, student):
    with pytest.raises(ValidationError):
        services.generate_exam(student, 30)
    with pytest.raises(ValidationError):
        services.generate_exam(student, 50)  # only 25 questions exist


def test_filters_narrow_the_pool(bank, student):
    assert services.filter_questions(university="uvas").count() == 25
    assert services.filter_questions(topic="antibacterials").count() == 12
    assert services.filter_questions(year=1999).count() == 0


def test_exam_flow_scoring_and_weak_topics(bank, student):
    api = APIClient()
    api.force_authenticate(student)
    r = api.post("/api/v1/study/exams/", {"size": 20, "subject": "pharmacology"}, format="json")
    assert r.status_code == 201, r.content
    eid = r.json()["id"]
    detail = api.get(f"/api/v1/study/exams/{eid}/").json()
    assert len(detail["questions"]) == 20
    assert "correct_option" not in detail["questions"][0]  # no answer leak before submit
    answers = {}
    for q in detail["questions"]:
        correct = Option.objects.get(question_id=q["id"], is_correct=True)
        wrong = Option.objects.filter(question_id=q["id"], is_correct=False).first()
        # answer correctly only for Anaesthetics
        answers[q["id"]] = correct.pk if q["topic"] == "Anaesthetics" else wrong.pk
    url = f"/api/v1/study/exams/{eid}/submit/"
    res = api.post(url, {"answers": answers}, format="json").json()
    expected = sum(1 for q in detail["questions"] if q["topic"] == "Anaesthetics")
    assert res["score"] == expected and res["total"] == 20
    assert res["weak_topics"] == ["Antibacterials"]
    after = api.get(f"/api/v1/study/exams/{eid}/").json()
    assert after["submitted"] and "explanation" in after["questions"][0]
    assert api.post(url, {"answers": answers}, format="json").status_code == 400
    assert len(api.get("/api/v1/study/exams/history/").json()) == 1


def test_cannot_read_or_submit_another_users_exam(bank, student):
    attempt = services.generate_exam(student, 20, rng=random.Random(1))
    other = APIClient()
    other.force_authenticate(User.objects.create_user("o", password="x"))
    assert other.get(f"/api/v1/study/exams/{attempt.pk}/").status_code == 404
    url = f"/api/v1/study/exams/{attempt.pk}/submit/"
    assert other.post(url, {"answers": {}}, format="json").status_code == 404


def test_answer_must_belong_to_question(bank, student):
    attempt = services.generate_exam(student, 20, rng=random.Random(2))
    row = attempt.answers.first()
    foreign = Option.objects.exclude(question_id=row.question_id).first()
    with pytest.raises(ValidationError):
        services.submit_exam(attempt, {row.question_id: foreign.pk})


def test_public_questions_hide_answers_and_bookmark_toggle(bank, student):
    anon = APIClient()
    data = anon.get("/api/v1/study/questions/?subject=pharmacology").json()
    assert data and "correct_option" not in data[0] and "explanation" not in data[0]
    api = APIClient()
    api.force_authenticate(student)
    qid = bank[0].pk
    assert api.post(f"/api/v1/study/questions/{qid}/bookmark/").json() == {"bookmarked": True}
    assert api.post(f"/api/v1/study/questions/{qid}/bookmark/").json() == {"bookmarked": False}
    report = f"/api/v1/study/questions/{qid}/report/"
    assert api.post(report, {"message": ""}, format="json").status_code == 400
    assert api.post(report, {"message": "Wrong key"}, format="json").status_code == 201
    assert anon.post(f"/api/v1/study/questions/{qid}/bookmark/").status_code in (401, 403)
