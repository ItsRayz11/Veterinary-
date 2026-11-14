import difflib

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsEditor
from apps.ai import client as ai
from apps.ai.triage import CLINICAL
from apps.automation import safe_http
from apps.core.crud import crud_views, simple_row
from apps.core.models import AuditLog
from apps.core.schema import untyped_schema
from apps.core.throttling import UserThrottle
from apps.species.models import Species

from . import trends
from .models import (
    Article,
    ArticleRevision,
    ArticleStatus,
    TopicBasis,
    TopicStatus,
    TopicSuggestion,
)


class SubmitThrottle(UserThrottle):
    scope = "submit"


MAX_OPEN_SUBMISSIONS = 5


def _public(a: Article, full=False) -> dict:
    d = {
        "slug": a.slug,
        "title": a.title,
        "excerpt": a.excerpt,
        "category": a.category,
        "tags": a.tag_list,
        "author": a.author_credit or a.author.username,
        "published_at": a.publish_at,
        "updated_at": a.updated_at,
        "meta_title": a.meta_title or a.title,
        "meta_description": a.meta_description or a.excerpt,
        "canonical_url": a.canonical_url,
        "ai_assisted": a.ai_assisted,
        "medical": a.medical,
    }
    if full:
        d["body"] = a.body
        d["references"] = a.reference_list
    return d


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def article_list(request):
    qs = Article.objects.public().select_related("author").order_by("-publish_at")
    if c := request.query_params.get("category"):
        qs = qs.filter(category__iexact=c)
    if t := request.query_params.get("tag"):
        qs = qs.filter(tags__icontains=t)
    return Response({"results": [_public(a) for a in qs[:100]]})


@untyped_schema
@api_view(["GET"])
@permission_classes([AllowAny])
def article_detail(request, slug):
    a = get_object_or_404(Article.objects.public().select_related("author"), slug=slug)
    related = (
        Article.objects.public()
        .filter(category=a.category)
        .exclude(pk=a.pk)
        .order_by("-publish_at")
        if a.category
        else Article.objects.none()
    )
    return Response(_public(a, full=True) | {"related": [_public(r) for r in related[:3]]})


@untyped_schema
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SubmitThrottle])
def article_submit(request):
    """A signed-in contributor sends an article for review. It is never public until approved."""
    if (
        Article.objects.filter(author=request.user, status=ArticleStatus.REVIEW).count()
        >= MAX_OPEN_SUBMISSIONS
    ):
        return Response(
            {"detail": "You already have several articles awaiting review."},
            status=http.HTTP_429_TOO_MANY_REQUESTS,
        )
    d = request.data
    a = Article(
        title=str(d.get("title", ""))[:200],
        excerpt=str(d.get("excerpt", ""))[:300],
        body=str(d.get("body", "")),
        category=str(d.get("category", ""))[:60],
        tags=str(d.get("tags", ""))[:200],
        references=str(d.get("references", "")),
        author=request.user,
        status=ArticleStatus.REVIEW,
    )
    a.medical = bool(CLINICAL.search(f"{a.title} {a.body}"))  # clinical claims need a vet reviewer
    try:
        a.clean()
        if len(a.body) < 200:
            raise ValidationError("Please write at least a few paragraphs (200+ characters).")
        a.full_clean(exclude=["slug"])
    except ValidationError as exc:
        return Response({"detail": "; ".join(exc.messages)}, status=http.HTTP_400_BAD_REQUEST)
    a.save()
    ArticleRevision.objects.create(
        article=a, number=1, title=a.title, body=a.body, edited_by=request.user
    )
    return Response({"detail": "Thank you. An editor will review it.", "id": a.pk}, status=201)


# ---------- staff ----------

FIELDS = [
    "title", "excerpt", "body", "category", "tags", "author_credit", "meta_title",
    "meta_description", "canonical_url", "references", "medical", "publish_at",
]  # fmt: skip


def _row(a: Article) -> dict:
    return simple_row(FIELDS)(a) | {
        "status": a.status,
        "slug": a.slug,
        "author": a.author.username,
        "ai_assisted": a.ai_assisted,
        "reviewed_by": a.reviewed_by.username if a.reviewed_by else None,
        "reject_reason": a.reject_reason,
        "revision": a.revision,
        "body": a.body,
        "links": a.outbound_links(),
    }


def _revise(article, request, created):
    if not created:
        article.revision += 1
        article.save(update_fields=["revision", "updated_at"])
    ArticleRevision.objects.get_or_create(
        article=article,
        number=article.revision,
        defaults={"title": article.title, "body": article.body, "edited_by": request.user},
    )
    # Any edit after approval pulls a published/scheduled article back for re-review.
    if not created and article.status in (ArticleStatus.PUBLISHED, ArticleStatus.SCHEDULED):
        article.status, article.reviewed_by = ArticleStatus.REVIEW, None
        article.save(update_fields=["status", "reviewed_by", "updated_at"])


def _set_author(article, request):
    article.author = request.user


articles, article_update = crud_views(
    Article, fields=FIELDS, perm=IsEditor, name="article", row=_row, on_create=_set_author,
    hidden=("body",),
    after_save=_revise, queryset=lambda: Article.objects.select_related("author", "reviewed_by"),
)  # fmt: skip


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def article_action(request, pk, action):
    a = Article.objects.filter(pk=pk).select_related("author").first()
    if a is None:
        return Response({"detail": "Not found."}, status=http.HTTP_404_NOT_FOUND)
    user = request.user
    now = timezone.now()
    if action == "check-links":
        out = []
        for url in a.outbound_links()[:10]:
            try:
                code, _, _ = safe_http.fetch(url, method="HEAD", timeout=5, deadline=None)
                out.append({"url": url, "status": code, "ok": 200 <= code < 400})
            except safe_http.FetchError as exc:
                out.append({"url": url, "status": None, "ok": False, "error": str(exc)[:100]})
        return Response({"results": out})
    if action in ("publish", "schedule"):
        if a.status == ArticleStatus.REJECTED:
            return Response({"detail": "Reopen it as a draft first."}, status=409)
        if a.medical and not user.can_approve_clinical:
            return Response(
                {"detail": "Clinical articles need a veterinarian reviewer or admin to approve."},
                status=http.HTTP_403_FORBIDDEN,
            )
        if a.medical and not a.reference_list:
            return Response({"detail": "Clinical articles need cited references."}, status=409)
        if len(a.body) < 200:
            return Response({"detail": "The article is too short to publish."}, status=409)
        if action == "schedule":
            if not a.publish_at or a.publish_at <= now:
                return Response({"detail": "Set a future publish date first."}, status=409)
            a.status = ArticleStatus.SCHEDULED
        else:
            a.status = ArticleStatus.PUBLISHED
            if not a.publish_at or a.publish_at > now:
                a.publish_at = now
        a.reviewed_by = user
    elif action == "submit":
        a.status = ArticleStatus.REVIEW
    elif action == "reject":
        a.status, a.reject_reason = (
            ArticleStatus.REJECTED,
            str(request.data.get("reason", ""))[:300],
        )
        if not a.reject_reason:
            return Response({"detail": "A reason is required."}, status=400)
        a.reviewed_by = None
    elif action in ("unpublish", "reopen"):
        a.status, a.reviewed_by = ArticleStatus.DRAFT, None
    else:
        return Response({"detail": "Unknown action."}, status=http.HTTP_404_NOT_FOUND)
    a.save()
    AuditLog.objects.create(
        actor=user, action=f"article_{action.replace('-', '_')}", object_type=a._meta.label,
        object_id=str(a.pk), after={"status": a.status, "medical": a.medical},
    )  # fmt: skip
    return Response(_row(a))


# ---------- editorial assistant ----------

TOPIC_FIELDS = ["title", "rationale", "evidence_url", "status"]
topics, topic_update = crud_views(
    TopicSuggestion, fields=TOPIC_FIELDS, perm=IsEditor, name="topic",
    row=simple_row(
        TOPIC_FIELDS, lambda t: {"basis": t.basis, "basis_label": t.get_basis_display()}
    ),
)  # fmt: skip


def _similar(title: str, existing: list[str]) -> bool:
    t = title.lower()
    return any(difflib.SequenceMatcher(None, t, e.lower()).ratio() > 0.8 for e in existing)


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def suggest_topics(request):
    """Gap-based ideas from VetRef's own data, plus model ideas if an AI route is configured.

    Each idea says what it is based on. Nothing here is trend data: VetRef has no trend feed
    registered, so no suggestion is labelled as one.
    """
    existing = list(Article.objects.values_list("title", flat=True)) + list(
        TopicSuggestion.objects.values_list("title", flat=True)
    )
    made, skipped = [], 0
    covered = " ".join(existing).lower()
    for sp in Species.objects.filter(parent__isnull=True)[:30]:
        if sp.name.lower() in covered:
            continue
        title = f"Veterinary medicines for {sp.name}: what to check before use"
        if _similar(title, existing):
            skipped += 1
            continue
        made.append(
            TopicSuggestion.objects.create(
                title=title,
                basis=TopicBasis.CATALOGUE_GAP,
                rationale=f"VetRef tracks {sp.name} but no article or idea mentions it yet.",
            )
        )
    trend_note = ""
    src, why = trends.source_ready()
    if src is None:
        trend_note = f"Trend ideas skipped: {why}"
    else:
        names = list(
            Species.objects.filter(parent__isnull=True).values_list("name", flat=True)[:25]
        )
        for t in trends.trending(names):
            title = f"{t['topic']}: a practical guide for veterinary learners"
            if _similar(title, existing + [m.title for m in made]):
                skipped += 1
                continue
            made.append(
                TopicSuggestion.objects.create(
                    title=title,
                    basis=TopicBasis.VERIFIED_TREND,
                    rationale=(
                        f"Wikipedia views for '{t['topic']}': {t['recent']:,} in the last 30 days "
                        f"vs {t['prior']:,} in the 30 before (+{t['growth_pct']}%). "
                        "General public interest, not veterinary-specific."
                    )[:400],
                    evidence_url=t["evidence_url"],
                )
            )
    ai_note = ""
    try:
        text = ai.run_task(
            "suggestions",
            "List 5 distinct veterinary-education blog topic titles, one per line, no numbering, "
            "no medical claims, no dosages. Existing titles to avoid: " + "; ".join(existing[:40]),
            actor=request.user,
        )
        for line in [ln.strip(" -*\t") for ln in text.splitlines() if ln.strip()][:5]:
            if _similar(line, existing + [m.title for m in made]):
                skipped += 1
                continue
            made.append(
                TopicSuggestion.objects.create(
                    title=line[:200],
                    basis=TopicBasis.MODEL,
                    rationale="AI model suggestion from existing titles; not based on data.",
                )
            )
    except ai.AIError as exc:
        ai_note = f"AI suggestions skipped: {exc}"
    return Response(
        {
            "created": len(made),
            "duplicates_skipped": skipped,
            "note": " ".join(n for n in (trend_note, ai_note) if n),
        },
        status=201,
    )


@untyped_schema
@api_view(["POST"])
@permission_classes([IsEditor])
def draft_from_topic(request, pk):
    """AI outline and draft. Saved as an unpublished, AI-assisted, medical-flagged draft."""
    t = get_object_or_404(TopicSuggestion, pk=pk)
    try:
        text = ai.run_task(
            "drafting",
            f"Write an outline and a short draft for a veterinary-education article titled "
            f"'{t.title}'. Do not state doses, treatments or regulatory facts. Mark every factual "
            "claim that needs a source with [citation needed]. Do not invent references or URLs.",
            actor=request.user,
        )
    except ai.AIError as exc:
        return Response({"detail": str(exc)}, status=http.HTTP_409_CONFLICT)
    a = Article(
        title=t.title, body=text, author=request.user, ai_assisted=True, medical=True,
        status=ArticleStatus.DRAFT,
    )  # fmt: skip
    a.clean()
    a.save()
    ArticleRevision.objects.create(
        article=a, number=1, title=a.title, body=a.body, edited_by=request.user
    )
    t.status = TopicStatus.ACCEPTED
    t.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        actor=request.user, action="article_ai_draft", object_type=a._meta.label,
        object_id=str(a.pk), after={"topic": t.pk},
    )  # fmt: skip
    return Response(_row(a), status=201)
