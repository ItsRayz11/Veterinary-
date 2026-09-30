"""Deterministic study helpers: Leitner scheduling and progress statistics."""

from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q

from .models import ExamAnswer, ExamAttempt, Flashcard, FlashcardProgress

# Days until the next review, by box after a correct answer moves the card there.
INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
MAX_BOX = 5
WEAK_PERCENT = 60
MIN_ANSWERS_FOR_WEAK = 3


def record_review(user, card: Flashcard, correct: bool, today: date) -> FlashcardProgress:
    """Correct: up one box (max 5). Wrong: back to box 1. Next due date follows the new box."""
    progress, _ = FlashcardProgress.objects.get_or_create(
        user=user, card=card, defaults={"box": 1, "due_on": today}
    )
    if correct:
        progress.box = min(progress.box + 1, MAX_BOX)
        progress.times_correct += 1
    else:
        progress.box = 1
        progress.times_wrong += 1
    progress.due_on = today + timedelta(days=INTERVAL_DAYS[progress.box])
    progress.save()
    return progress


def due_cards(user, today: date, limit: int = 20):
    """Cards already in a box and due, then unseen public cards, up to `limit`."""
    seen = FlashcardProgress.objects.filter(user=user)
    due_ids = list(
        seen.filter(due_on__lte=today, card__in=Flashcard.objects.public())
        .order_by("due_on", "box")
        .values_list("card_id", flat=True)[:limit]
    )
    new_ids = []
    if len(due_ids) < limit:
        new_ids = list(
            Flashcard.objects.public()
            .exclude(pk__in=seen.values("card_id"))
            .values_list("pk", flat=True)[: limit - len(due_ids)]
        )
    order = {pk: i for i, pk in enumerate(due_ids + new_ids)}
    cards = Flashcard.objects.filter(pk__in=order).select_related("topic__subject")
    return sorted(cards, key=lambda c: order[c.pk])


def progress_summary(user) -> dict:
    """Exam scores over time and accuracy per subject/topic from submitted exams."""
    attempts = list(
        ExamAttempt.objects.filter(user=user, submitted_at__isnull=False)
        .order_by("submitted_at")
        .prefetch_related("answers")
    )
    history = []
    for a in attempts:
        total = len(a.answers.all())
        if total:
            history.append(
                {
                    "id": a.pk,
                    "date": a.submitted_at,
                    "score": a.score,
                    "total": total,
                    "percent": round(100 * (a.score or 0) / total),
                }
            )
    rows = ExamAnswer.objects.filter(
        attempt__user=user, attempt__submitted_at__isnull=False
    ).exclude(Q(is_correct__isnull=True))
    by_subject: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_topic: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for is_correct, subject, topic in rows.values_list(
        "is_correct", "question__topic__subject__name", "question__topic__name"
    ):
        for bucket in (by_subject[subject], by_topic[(subject, topic)]):
            bucket[1] += 1
            bucket[0] += bool(is_correct)
    subjects = [
        {"subject": s, "correct": c, "total": n, "percent": round(100 * c / n)}
        for s, (c, n) in sorted(by_subject.items())
    ]
    weak = [
        {"subject": s, "topic": t, "correct": c, "total": n, "percent": round(100 * c / n)}
        for (s, t), (c, n) in by_topic.items()
        if n >= MIN_ANSWERS_FOR_WEAK and round(100 * c / n) < WEAK_PERCENT
    ]
    weak.sort(key=lambda w: w["percent"])
    return {"history": history, "subjects": subjects, "weak_topics": weak}
