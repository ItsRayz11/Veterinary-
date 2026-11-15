from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.reference_data import UNIVERSITY_SOURCES
from apps.countries.models import Country
from apps.universities import importer, sync


class Command(BaseCommand):
    help = (
        "Import veterinary schools from Wikipedia/Wikidata as unreviewed records. Existing records "
        "that an editor has already reviewed are left untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument("--country", action="append", help="ISO2, repeatable. Default: all")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        wanted = [c.upper() for c in (opts["country"] or UNIVERSITY_SOURCES)]
        unknown = [c for c in wanted if c not in UNIVERSITY_SOURCES]
        if unknown:
            raise CommandError(f"No category mapping for: {', '.join(unknown)}")
        for iso2 in wanted:
            country = Country.objects.filter(iso2=iso2).first()
            if not country:
                self.stderr.write(f"{iso2}: country not in the database, skipped")
                continue
            rows = importer.collect(importer.api_fetch, iso2)
            created = updated = skipped = 0
            with transaction.atomic():
                for row in rows:
                    if opts["dry_run"]:
                        self.stdout.write(f"  {iso2} {row['name']}")
                        continue
                    result = sync.store_row(country, row)
                    created += result == "created"
                    updated += result == "updated"
                    skipped += result == "skipped"
            self.stdout.write(f"{iso2}: {created} created, {updated} updated, {skipped} skipped")
