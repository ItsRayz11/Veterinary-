"""Import a product list through the reviewed pipeline from the command line.

    python manage.py import_products <adapter> <file> --country PK --source-title "..." \
        --publisher "..." --url "..." --license-note "..." [--dry-run] [--no-approve]

Adapters: standard (already in the import format), drap-vet-applications, drap-vet-biologicals.
Everything is created as UNREVIEWED (`needs_verification`) and stays hidden until a veterinarian
reviewer promotes it. `--dry-run` cleans and reports without touching the database.
"""

import hashlib
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.countries.models import Country
from apps.ingestion import services
from apps.ingestion.adapters import drap
from apps.ingestion.models import ImportBatch

ADAPTERS = {
    "drap-vet-applications": drap.clean_vet_applications,
    "drap-vet-biologicals": drap.clean_vet_biologicals,
}
IMPORT_USER = "import-bot"


def import_user():
    """The account that appears in audit logs for command-line imports (never able to sign in)."""
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=IMPORT_USER, defaults={"role": "editor"})
    if user.has_usable_password():
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("adapter", choices=[*ADAPTERS, "standard"])
        parser.add_argument("file", type=Path)
        parser.add_argument("--country", required=True, help="ISO 3166 alpha-2 code, e.g. PK")
        parser.add_argument("--source-title", required=True)
        parser.add_argument("--publisher", default="")
        parser.add_argument("--url", default="")
        parser.add_argument("--license-note", required=True)
        parser.add_argument("--source-type", default="regulatory")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-approve", action="store_true", help="stage only")
        parser.add_argument(
            "--shard",
            help="i/n: only approve rows with id %% n == i (run n processes for a big batch)",
        )

    def handle(self, *args, **opts):
        path: Path = opts["file"]
        if not path.exists():
            raise CommandError(f"No such file: {path}")
        text = path.read_text(encoding="utf-8-sig")
        if opts["adapter"] == "standard":
            csv_text, report = text, {}
        else:
            cleaned = ADAPTERS[opts["adapter"]](text)
            csv_text, report = drap.to_csv(cleaned.rows), cleaned.report
        self.stdout.write("Cleaning report: " + json.dumps(report, indent=1))
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing was written."))
            return
        country = Country.objects.filter(iso2=opts["country"].upper()).first()
        if country is None:
            raise CommandError(f"Unknown country {opts['country']!r}; run seed_reference first.")
        user = import_user()
        checksum = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
        batch = ImportBatch.objects.filter(
            kind="products", country=country, checksum=checksum
        ).first()
        if batch is not None:
            # An interrupted earlier run: continue approving that same batch instead of refusing.
            self.stdout.write(self.style.WARNING(f"Resuming existing batch #{batch.pk}."))
        else:
            try:
                batch = services.stage_batch(
                    user=user,
                    country=country,
                    source_data={
                        "title": opts["source_title"],
                        "publisher": opts["publisher"],
                        "url": opts["url"],
                        "license_note": opts["license_note"],
                        "source_type": opts["source_type"],
                    },
                    csv_text=csv_text,
                    file_name=path.name,
                )
            except ValidationError as exc:
                raise CommandError(" ".join(exc.messages)) from exc
        counts = dict(
            batch.rows.values_list("status").annotate(n=Count("pk")).values_list("status", "n")
        )
        self.stdout.write(f"Staged batch #{batch.pk}: {counts}")
        if opts["no_approve"]:
            return
        shard = None
        if opts["shard"]:
            try:
                index, count = (int(x) for x in opts["shard"].split("/"))
                if not 0 <= index < count:
                    raise ValueError
            except ValueError as exc:
                raise CommandError("--shard must look like i/n, for example 0/8") from exc
            shard = (index, count)
        approved = skipped = 0
        stalled = 0
        while True:
            result = services.approve_clean(batch, user, shard=shard)
            approved += result["approved"]
            skipped += result["skipped"]
            self.stdout.write(
                f"  approved {approved}, flagged {skipped}, retried {result['retried']}, "
                f"remaining {result['remaining']}"
            )
            if result["remaining"] == 0:
                break
            stalled = stalled + 1 if (result["approved"] + result["skipped"]) == 0 else 0
            if stalled >= 3:  # only lost races for several passes: stop, a later run will finish
                break
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {approved} products created as UNREVIEWED (hidden until reviewed); "
                f"{skipped} rows flagged for staff (see Imports tab, batch #{batch.pk})."
            )
        )
