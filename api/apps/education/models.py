from django.conf import settings
from django.db import models

from apps.core.models import PublishableModel, TimeStampedModel
from apps.core.text import unique_slug


class Subject(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Subject, self.name, self)
        super().save(*args, **kwargs)


class Topic(TimeStampedModel):
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="topics")
    name = models.CharField(max_length=160)
    slug = models.SlugField(editable=False)
    # Optional link to the drug encyclopedia so study and reference connect.
    generic = models.ForeignKey(
        "pharma.Generic", null=True, blank=True, on_delete=models.SET_NULL, related_name="topics"
    )

    class Meta:
        ordering = ["subject__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["subject", "name"], name="uniq_topic_in_subject"),
            models.UniqueConstraint(fields=["subject", "slug"], name="uniq_topic_slug_in_subject"),
        ]

    def __str__(self):
        return f"{self.subject}: {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify

            limit = self._meta.get_field("slug").max_length or 50
            self.slug = slugify(self.name)[:limit] or "topic"
        super().save(*args, **kwargs)


class Difficulty(models.IntegerChoices):
    EASY = 1
    MEDIUM = 2
    HARD = 3


class Question(PublishableModel):
    """Single-best-answer MCQ. Structured, filterable, never a PDF."""

    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="questions")
    stem = models.TextField()
    explanation = models.TextField(blank=True)
    difficulty = models.PositiveSmallIntegerField(
        choices=Difficulty.choices, default=Difficulty.MEDIUM
    )
    country = models.ForeignKey(
        "countries.Country", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    exam = models.CharField(max_length=120, blank=True)
    university = models.CharField(max_length=160, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    source = models.ForeignKey(
        "sources.Source", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta(PublishableModel.Meta):
        indexes = [models.Index(fields=["topic", "difficulty"])]

    def __str__(self):
        return self.stem[:60]

    def validate_publishable(self):
        from .services import validate_question_ready

        validate_question_ready(self)


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=1)
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["label"]
        constraints = [
            models.UniqueConstraint(fields=["question", "label"], name="uniq_option_label"),
            models.UniqueConstraint(
                fields=["question"],
                condition=models.Q(is_correct=True),
                name="one_correct_option_per_question",
            ),
        ]

    def __str__(self):
        return f"{self.label}. {self.text[:40]}"


class PastPaper(TimeStampedModel):
    """Index entry pointing to a legally available paper. We never host copyrighted papers."""

    university = models.CharField(max_length=160)
    degree = models.CharField(max_length=80)
    course = models.CharField(max_length=160)
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL)
    year = models.PositiveSmallIntegerField()
    semester = models.CharField(max_length=20, blank=True)
    exam_type = models.CharField(max_length=40, blank=True)
    country = models.ForeignKey(
        "countries.Country", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    legal_source_url = models.URLField()
    license_note = models.CharField(max_length=200, help_text="Why linking/using this is allowed")
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-year", "university"]

    def __str__(self):
        return f"{self.university} {self.course} {self.year}"


class ExamAttempt(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exam_attempts"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ExamAnswer(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="+")
    selected = models.ForeignKey(
        Option, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    is_correct = models.BooleanField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="uniq_answer_per_question")
        ]

    def __str__(self):
        return f"attempt {self.attempt_id} q{self.question_id}"


class Bookmark(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="question_bookmarks"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "question"], name="uniq_bookmark")]


class QuestionReport(TimeStampedModel):
    """A user flagging an error in a question. Handled by moderators/editors."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    message = models.CharField(max_length=500)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["resolved", "-created_at"]


class Flashcard(PublishableModel):
    """Front/back study card. Public only after review with a linked source."""

    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="flashcards")
    front = models.CharField(max_length=500)
    back = models.TextField()

    class Meta(PublishableModel.Meta):
        ordering = ["topic__subject__name", "topic__name", "id"]

    def __str__(self):
        return self.front[:60]


class FlashcardProgress(TimeStampedModel):
    """Leitner box per user and card. Scheduling is deterministic (see study_tools)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="flashcard_progress"
    )
    card = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name="progress")
    box = models.PositiveSmallIntegerField(default=1)
    due_on = models.DateField()
    times_correct = models.PositiveIntegerField(default=0)
    times_wrong = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "card"], name="uniq_progress_per_card"),
            models.CheckConstraint(
                condition=models.Q(box__gte=1) & models.Q(box__lte=5), name="flashcard_box_1_5"
            ),
        ]


class Lesson(PublishableModel):
    """Short study note. Original text or a summary written by editors, with sources linked."""

    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="lessons")
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, editable=False)
    body = models.TextField(help_text="Plain text; blank lines separate paragraphs.")

    class Meta(PublishableModel.Meta):
        ordering = ["topic__subject__name", "topic__name", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Lesson, self.title, self)
        super().save(*args, **kwargs)


class BookReference(TimeStampedModel):
    """A recommended book, cited only (never its text)."""

    title = models.CharField(max_length=300)
    authors = models.CharField(max_length=300, blank=True)
    edition = models.CharField(max_length=60, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL)
    url = models.URLField(blank=True, help_text="Publisher or library page, not a pirated copy")
    note = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
