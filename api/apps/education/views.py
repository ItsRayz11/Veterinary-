from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.schema import untyped_schema
from apps.pharma.serializers import source_payload
from apps.sources.models import sources_for

from . import services, study_tools
from .models import (
    Bookmark,
    BookReference,
    ExamAttempt,
    Flashcard,
    Lesson,
    PastPaper,
    Question,
    QuestionReport,
    Subject,
)

FILTER_KEYS = ("subject", "topic", "university", "exam", "country", "year", "difficulty")


def _filters(params) -> dict:
    return {k: params[k] for k in FILTER_KEYS if params.get(k)}


def _question_payload(q: Question, reveal: bool) -> dict:
    data = {
        "id": q.pk,
        "stem": q.stem,
        "topic": q.topic.name,
        "subject": q.topic.subject.slug,
        "difficulty": q.difficulty,
        "options": [{"id": o.pk, "label": o.label, "text": o.text} for o in q.options.all()],
    }
    if reveal:
        data["correct_option"] = next((o.pk for o in q.options.all() if o.is_correct), None)
        data["explanation"] = q.explanation
    return data


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def subjects(request):
    return Response(
        [
            {
                "slug": s.slug,
                "name": s.name,
                "topics": [{"slug": t.slug, "name": t.name} for t in s.topics.all()],
            }
            for s in Subject.objects.prefetch_related("topics")
        ]
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def questions(request):
    qs = services.filter_questions(**_filters(request.query_params)).prefetch_related("options")
    return Response([_question_payload(q, reveal=False) for q in qs[:50]])


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def past_papers(request):
    qs = PastPaper.objects.filter(is_published=True)
    for key in ("university", "year", "course"):
        if request.query_params.get(key):
            qs = qs.filter(**{f"{key}__iexact": request.query_params[key]})
    return Response(
        [
            {
                "university": p.university,
                "degree": p.degree,
                "course": p.course,
                "year": p.year,
                "semester": p.semester,
                "exam_type": p.exam_type,
                "url": p.legal_source_url,
                "license_note": p.license_note,
            }
            for p in qs
        ]
    )


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_exam(request):
    try:
        size = int(request.data.get("size", 0))
        attempt = services.generate_exam(request.user, size, **_filters(request.data))
    except (ValueError, DjangoValidationError) as exc:
        raise ValidationError({"exam": getattr(exc, "messages", [str(exc)])[0]}) from exc
    return Response({"id": attempt.pk, "total": attempt.answers.count()}, status=201)


@untyped_schema
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exam_detail(request, pk):
    attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
    submitted = attempt.submitted_at is not None
    rows = attempt.answers.select_related("question__topic__subject", "selected").prefetch_related(
        "question__options"
    )
    items = []
    for r in rows:
        item = _question_payload(r.question, reveal=submitted)
        if submitted:
            item.update({"selected": r.selected_id, "is_correct": r.is_correct})
        items.append(item)
    return Response(
        {"id": attempt.pk, "submitted": submitted, "score": attempt.score, "questions": items}
    )


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_exam(request, pk):
    attempt = get_object_or_404(ExamAttempt, pk=pk, user=request.user)
    try:
        raw = request.data.get("answers", {})
        answers = {int(k): int(v) for k, v in raw.items()}
        return Response(services.submit_exam(attempt, answers))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({"answers": "Answers must map question ids to option ids."}) from exc
    except DjangoValidationError as exc:
        raise ValidationError({"exam": exc.messages[0]}) from exc


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bookmark(request, pk):
    q = get_object_or_404(Question.objects.public(), pk=pk)
    obj, created = Bookmark.objects.get_or_create(user=request.user, question=q)
    if not created:
        obj.delete()
    return Response({"bookmarked": created})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def report_question(request, pk):
    q = get_object_or_404(Question.objects.public(), pk=pk)
    message = str(request.data.get("message", "")).strip()
    if not message:
        raise ValidationError({"message": "Describe the problem."})
    QuestionReport.objects.create(question=q, reporter=request.user, message=message[:500])
    return Response(status=201)


@untyped_schema
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def history(request):
    rows = ExamAttempt.objects.filter(user=request.user, submitted_at__isnull=False)[:50]
    return Response(
        [
            {"id": a.pk, "date": a.submitted_at, "score": a.score, "total": a.answers.count()}
            for a in rows
        ]
    )


def _flashcard_payload(c) -> dict:
    return {
        "id": c.pk,
        "front": c.front,
        "back": c.back,
        "topic": c.topic.name,
        "subject": c.topic.subject.slug,
    }


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def flashcards(request):
    qs = Flashcard.objects.public().select_related("topic__subject")
    if request.query_params.get("subject"):
        qs = qs.filter(topic__subject__slug=request.query_params["subject"])
    if request.query_params.get("topic"):
        qs = qs.filter(topic__slug=request.query_params["topic"])
    return Response([_flashcard_payload(c) for c in qs[:100]])


@untyped_schema
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def flashcards_due(request):
    cards = study_tools.due_cards(request.user, timezone.localdate())
    return Response([_flashcard_payload(c) for c in cards])


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def flashcard_review(request, pk):
    card = get_object_or_404(Flashcard.objects.public(), pk=pk)
    correct = request.data.get("correct")
    if not isinstance(correct, bool):
        raise ValidationError({"correct": "Send true or false."})
    p = study_tools.record_review(request.user, card, correct, timezone.localdate())
    return Response({"box": p.box, "due_on": p.due_on})


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def lessons(request):
    qs = Lesson.objects.public().select_related("topic__subject")
    if request.query_params.get("subject"):
        qs = qs.filter(topic__subject__slug=request.query_params["subject"])
    return Response(
        [
            {
                "slug": x.slug,
                "title": x.title,
                "topic": x.topic.name,
                "subject": x.topic.subject.name,
            }
            for x in qs
        ]
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def lesson_detail(request, slug):
    lesson = get_object_or_404(Lesson.objects.public().select_related("topic__subject"), slug=slug)
    return Response(
        {
            "slug": lesson.slug,
            "title": lesson.title,
            "topic": lesson.topic.name,
            "subject": lesson.topic.subject.name,
            "body": lesson.body,
            "sources": source_payload([(s, "") for s in sources_for(lesson)]),
            "status": {
                "code": lesson.review_status,
                "is_development_data": lesson.is_development_data,
            },
        }
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def books(request):
    qs = BookReference.objects.filter(is_published=True).select_related("subject")
    return Response(
        [
            {
                "title": b.title,
                "authors": b.authors,
                "edition": b.edition,
                "isbn": b.isbn,
                "subject": b.subject.name if b.subject else None,
                "url": b.url,
                "note": b.note,
            }
            for b in qs
        ]
    )


@untyped_schema
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def progress(request):
    return Response(study_tools.progress_summary(request.user))
