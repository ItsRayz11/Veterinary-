from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import Bookmark, ExamAttempt, PastPaper, Question, QuestionReport, Subject

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


@api_view(["GET"])
@permission_classes([AllowAny])
def questions(request):
    qs = services.filter_questions(**_filters(request.query_params)).prefetch_related("options")
    return Response([_question_payload(q, reveal=False) for q in qs[:50]])


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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_exam(request):
    try:
        size = int(request.data.get("size", 0))
        attempt = services.generate_exam(request.user, size, **_filters(request.data))
    except (ValueError, DjangoValidationError) as exc:
        raise ValidationError({"exam": getattr(exc, "messages", [str(exc)])[0]}) from exc
    return Response({"id": attempt.pk, "total": attempt.answers.count()}, status=201)


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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bookmark(request, pk):
    q = get_object_or_404(Question.objects.public(), pk=pk)
    obj, created = Bookmark.objects.get_or_create(user=request.user, question=q)
    if not created:
        obj.delete()
    return Response({"bookmarked": created})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def report_question(request, pk):
    q = get_object_or_404(Question.objects.public(), pk=pk)
    message = str(request.data.get("message", "")).strip()
    if not message:
        raise ValidationError({"message": "Describe the problem."})
    QuestionReport.objects.create(question=q, reporter=request.user, message=message[:500])
    return Response(status=201)


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
