"""Bulk intake of multiple-choice questions from a CSV, for reviewers who hold the rights to them.

The importer never decides that a question is correct or that its content may be used: the caller
must state the source and the licence/permission, every question lands as `needs_verification`
(hidden), and a veterinarian reviewer still has to sign each one off.

Columns (header names are case-insensitive):
    subject, topic, stem, option_a .. option_e, correct (a letter), explanation (optional),
    difficulty (easy|medium|hard, optional), university, exam, year, country (ISO2) (optional)
"""

import csv
import io
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import AuditLog, ReviewStatus
from apps.countries.models import Country
from apps.sources.models import Source

from .models import Difficulty, Option, Question, Subject, Topic

MAX_ROWS = 2000
LETTERS = "abcde"
DIFFICULTY = {"easy": Difficulty.EASY, "medium": Difficulty.MEDIUM, "hard": Difficulty.HARD}
REQUIRED = ("subject", "topic", "stem", "option_a", "option_b", "correct")


@dataclass
class Result:
    created: int = 0
    skipped: list[str] = field(default_factory=list)  # human-readable reasons, one per bad row


def _row_error(n: int, message: str) -> str:
    return f"Row {n}: {message}"


def parse(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames:
        raise ValidationError("The file is empty.")
    names = {f.strip().lower(): f for f in reader.fieldnames}
    missing = [c for c in REQUIRED if c not in names]
    if missing:
        raise ValidationError(f"Missing required column(s): {', '.join(missing)}.")
    rows = []
    try:
        for raw in reader:
            rows.append({k: (raw.get(orig) or "").strip() for k, orig in names.items()})
            if len(rows) > MAX_ROWS:
                raise ValidationError(f"More than {MAX_ROWS} rows; split the file.")
    except csv.Error as exc:
        raise ValidationError(f"The file is not valid CSV: {exc}") from exc
    if not rows:
        raise ValidationError("The file has a header but no questions.")
    return rows


def validate_row(n: int, row: dict) -> str | None:
    """None when the row is usable, otherwise the reason it is not."""
    if not (row["subject"] and row["topic"] and row["stem"]):
        return _row_error(n, "subject, topic and question text are required.")
    options = {c: row.get(f"option_{c}", "") for c in LETTERS if row.get(f"option_{c}", "")}
    if len(options) < 2:
        return _row_error(n, "at least two options are required.")
    if not (len(row["correct"]) == 1 and row["correct"].lower() in options):
        return _row_error(n, "'correct' must be the letter of one of the filled options.")
    if row.get("difficulty") and row["difficulty"].lower() not in DIFFICULTY:
        return _row_error(n, "difficulty must be easy, medium or hard.")
    if row.get("year") and not (row["year"].isdigit() and 1900 <= int(row["year"]) <= 2100):
        return _row_error(n, "year must be a 4-digit year.")
    return None


@transaction.atomic
def import_questions(
    *, user, csv_text: str, source_title: str, licence_note: str, publisher: str = "", url: str = ""
) -> Result:
    """Create unreviewed questions. Rows with problems are skipped and reported; valid rows load."""
    if not source_title.strip():
        raise ValidationError("A source title is required.")
    if not licence_note.strip():
        raise ValidationError(
            "State the licence or permission that lets you use these questions before importing."
        )
    if not (url.strip() or publisher.strip()):
        raise ValidationError("Give the source URL or publisher so the questions can be traced.")
    rows = parse(csv_text)
    source = Source(
        source_type="other",
        title=source_title.strip(),
        publisher=publisher.strip(),
        url=url.strip(),
        license_note=licence_note.strip(),
    )
    source.full_clean()
    source.save()
    result = Result()
    countries = {c.iso2: c for c in Country.objects.all()}
    for n, row in enumerate(rows, start=2):  # row 1 is the header
        problem = validate_row(n, row)
        if problem:
            result.skipped.append(problem)
            continue
        subject, _ = Subject.objects.get_or_create(name=row["subject"])
        topic, _ = Topic.objects.get_or_create(subject=subject, name=row["topic"])
        question = Question.objects.create(
            topic=topic,
            stem=row["stem"],
            explanation=row.get("explanation", ""),
            difficulty=DIFFICULTY.get(row.get("difficulty", "").lower(), Difficulty.MEDIUM),
            country=countries.get(row.get("country", "").upper()),
            exam=row.get("exam", "")[:120],
            university=row.get("university", "")[:160],
            year=int(row["year"]) if row.get("year") else None,
            source=source,
            review_status=ReviewStatus.NEEDS_VERIFICATION,
        )
        for letter in LETTERS:
            text = row.get(f"option_{letter}", "")
            if text:
                Option.objects.create(
                    question=question,
                    label=letter.upper(),
                    text=text[:500],
                    is_correct=(letter == row["correct"].lower()),
                )
        result.created += 1
    AuditLog.objects.create(
        actor=user,
        action="questions_imported",
        object_type=Question._meta.label,
        object_id=str(source.pk),
        after={"created": result.created, "skipped": len(result.skipped)},
        reason=licence_note[:300],
    )
    return result
