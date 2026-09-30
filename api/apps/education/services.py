"""Exam generation, scoring and question validation."""

import random
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import ExamAnswer, ExamAttempt, Option, Question

ALLOWED_SIZES = (20, 50, 100)


def validate_question_ready(question: Question) -> None:
    """A question may only be published with >= 2 options and exactly one correct option."""
    opts = list(question.options.all())
    if len(opts) < 2:
        raise ValidationError("A question needs at least two options.")
    if sum(o.is_correct for o in opts) != 1:
        raise ValidationError("A question needs exactly one correct option.")


def filter_questions(
    subject=None, topic=None, university=None, exam=None, country=None, year=None, difficulty=None
):
    qs = Question.objects.public().select_related("topic__subject")
    if subject:
        qs = qs.filter(topic__subject__slug=subject)
    if topic:
        qs = qs.filter(topic__slug=topic)
    if university:
        qs = qs.filter(university__iexact=university)
    if exam:
        qs = qs.filter(exam__iexact=exam)
    if country:
        qs = qs.filter(country__iso2=country)
    if year:
        qs = qs.filter(year=year)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    return qs


@transaction.atomic
def generate_exam(user, size: int, rng: random.Random | None = None, **filters) -> ExamAttempt:
    if size not in ALLOWED_SIZES:
        raise ValidationError(f"Exam size must be one of {ALLOWED_SIZES}.")
    ids = list(filter_questions(**filters).values_list("pk", flat=True))
    if len(ids) < size:
        raise ValidationError(
            f"Only {len(ids)} matching questions are available; {size} requested."
        )
    chosen = (rng or random).sample(ids, size)
    attempt = ExamAttempt.objects.create(user=user)
    ExamAnswer.objects.bulk_create([ExamAnswer(attempt=attempt, question_id=q) for q in chosen])
    return attempt


@transaction.atomic
def submit_exam(attempt: ExamAttempt, answers: dict[int, int]) -> dict:
    """answers: {question_id: option_id}. Returns score, per-topic breakdown, weak topics."""
    if attempt.submitted_at:
        raise ValidationError("This exam was already submitted.")
    rows = list(attempt.answers.select_related("question__topic"))
    exam_question_ids = {r.question_id for r in rows}
    options = {o.pk: o for o in Option.objects.filter(pk__in=set(answers.values()))}
    for qid, oid in answers.items():
        opt = options.get(oid)
        if qid not in exam_question_ids:
            raise ValidationError("An answer refers to a question that is not in this exam.")
        if opt is None or opt.question_id != qid:
            raise ValidationError("An answer does not belong to its question.")
    correct = 0
    by_topic: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        opt = options.get(answers.get(row.question_id))
        row.selected = opt
        row.is_correct = bool(opt and opt.is_correct)
        row.save(update_fields=["selected", "is_correct"])
        correct += row.is_correct
        t = by_topic[row.question.topic.name]
        t[1] += 1
        t[0] += row.is_correct
    attempt.score = correct
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=["score", "submitted_at", "updated_at"])
    topics = [
        {"topic": name, "correct": c, "total": n, "percent": round(100 * c / n)}
        for name, (c, n) in by_topic.items()
    ]
    return {
        "score": correct,
        "total": len(rows),
        "topics": sorted(topics, key=lambda t: t["percent"]),
        "weak_topics": [t["topic"] for t in topics if t["percent"] < 60],
    }
