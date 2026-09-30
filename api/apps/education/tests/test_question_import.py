"""Question intake: rights must be stated, everything lands hidden, bad rows are reported."""

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.education import importer
from apps.education.models import Option, Question

HEADER = "subject,topic,stem,option_a,option_b,option_c,correct,explanation,difficulty,year\n"
GOOD = (
    HEADER
    + 'Pharmacology,Antibacterials,"Which class is enrofloxacin?",Fluoroquinolone,Macrolide,Beta-lactam,a,"Sample explanation",hard,2024\n'
    + 'Pharmacology,Antibacterials,"Second question?",Yes,No,,b,,easy,\n'
)


@pytest.fixture
def user(db):
    return User.objects.create_user("editor", password="x", role=Role.EDITOR)


def run(user, text=GOOD, **kw):
    args = dict(
        user=user,
        csv_text=text,
        source_title="Original questions written by Dr Example",
        licence_note="Written by the reviewer; released to this platform",
        publisher="Dr Example",
    )
    args.update(kw)
    return importer.import_questions(**args)


def test_questions_are_created_hidden_with_one_correct_option_and_a_source(user):
    result = run(user)
    assert result.created == 2 and result.skipped == []
    q = Question.objects.get(stem="Which class is enrofloxacin?")
    assert q.review_status == "needs_verification" and not q.is_public
    assert q.difficulty == 3 and q.year == 2024 and q.source.license_note.startswith("Written by")
    assert list(q.options.values_list("label", "is_correct")) == [
        ("A", True),
        ("B", False),
        ("C", False),
    ]
    assert Question.objects.public().count() == 0


def test_the_licence_or_permission_must_be_stated(user):
    with pytest.raises(ValidationError, match="licence or permission"):
        run(user, licence_note="  ")
    with pytest.raises(ValidationError, match="source title"):
        run(user, source_title="")
    with pytest.raises(ValidationError, match="URL or publisher"):
        run(user, publisher="", url="")
    assert Question.objects.count() == 0


@pytest.mark.parametrize(
    ("row", "fragment"),
    [
        ("Pharm,Topic,,A1,B1,,a,,,", "required"),
        ("Pharm,Topic,Stem,OnlyOne,,,a,,,", "two options"),
        ("Pharm,Topic,Stem,A1,B1,,c,,,", "letter of one of the filled options"),
        ("Pharm,Topic,Stem,A1,B1,,ab,,,", "letter of one of the filled options"),
        ("Pharm,Topic,Stem,A1,B1,,a,,impossible,", "easy, medium or hard"),
        ("Pharm,Topic,Stem,A1,B1,,a,,,20x4", "4-digit year"),
    ],
)
def test_bad_rows_are_skipped_with_a_reason_and_good_rows_still_load(user, row, fragment):
    result = run(user, HEADER + row + "\n" + GOOD.split("\n", 1)[1])
    assert result.created == 2 and len(result.skipped) == 1
    assert fragment in result.skipped[0] and result.skipped[0].startswith("Row 2")


def test_unusable_files_are_refused(user):
    with pytest.raises(ValidationError, match="empty"):
        run(user, "")
    with pytest.raises(ValidationError, match="Missing required column"):
        run(user, "subject,topic,stem\nA,B,C\n")
    with pytest.raises(ValidationError, match="no questions"):
        run(user, HEADER)


def test_command_dry_run_writes_nothing_and_real_run_needs_a_licence(user, tmp_path, capsys):
    f = tmp_path / "q.csv"
    f.write_text(GOOD, encoding="utf-8")
    call_command(
        "import_questions", str(f), "--source-title", "T", "--licence-note", "n", "--dry-run"
    )
    assert Question.objects.count() == 0
    assert "2 rows read, 0 with problems" in capsys.readouterr().out
    call_command(
        "import_questions", str(f), "--source-title", "T", "--licence-note", "n", "--publisher", "P"
    )
    assert Question.objects.count() == 2 and Option.objects.count() == 5
    assert User.objects.get(username="import-bot").has_usable_password() is False


def test_imported_questions_cannot_be_published_without_a_reviewer(user):
    from django.core.exceptions import PermissionDenied

    from apps.core.review import set_review_status

    run(user)
    q = Question.objects.first()
    with pytest.raises(PermissionDenied):
        set_review_status(q, "verified", user)  # an editor cannot sign off clinical content
