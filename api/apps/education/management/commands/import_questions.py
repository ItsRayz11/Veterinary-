"""Load multiple-choice questions you hold the rights to, as UNREVIEWED records.

    python manage.py import_questions questions.csv --source-title "..." --licence-note "..." \
        [--publisher "..."] [--url "..."] [--dry-run]

See apps/education/importer.py for the columns. Nothing becomes public: a veterinarian reviewer
must sign off every question (and it needs a source and exactly one correct option).
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.education import importer

IMPORT_USER = "import-bot"


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--source-title", required=True)
        parser.add_argument("--licence-note", required=True)
        parser.add_argument("--publisher", default="")
        parser.add_argument("--url", default="")
        parser.add_argument("--dry-run", action="store_true", help="validate rows, write nothing")

    def handle(self, *args, **opts):
        path: Path = opts["file"]
        if not path.exists():
            raise CommandError(f"No such file: {path}")
        text = path.read_text(encoding="utf-8-sig")
        try:
            rows = importer.parse(text)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        problems = [p for n, r in enumerate(rows, start=2) if (p := importer.validate_row(n, r))]
        self.stdout.write(f"{len(rows)} rows read, {len(problems)} with problems.")
        for line in problems[:20]:
            self.stdout.write(self.style.WARNING("  " + line))
        if opts["dry_run"]:
            self.stdout.write("Dry run: nothing was written.")
            return
        User = get_user_model()
        user, _ = User.objects.get_or_create(username=IMPORT_USER, defaults={"role": "editor"})
        if user.has_usable_password():
            user.set_unusable_password()
            user.save(update_fields=["password"])
        try:
            result = importer.import_questions(
                user=user,
                csv_text=text,
                source_title=opts["source_title"],
                licence_note=opts["licence_note"],
                publisher=opts["publisher"],
                url=opts["url"],
            )
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{result.created} questions created as UNREVIEWED (hidden until a veterinarian "
                f"reviewer signs each off); {len(result.skipped)} rows skipped."
            )
        )
