from django.core.management.base import BaseCommand

from apps.automation import pipeline
from apps.core.review import publishable_models
from apps.sources import linking


class Command(BaseCommand):
    help = (
        "Link every record's raw source URL to a registry Source (deduplicated and validated) and "
        "register its image references. Adds data only: record fields, review status and original "
        "URLs are never changed. Safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count what would be linked")

    def handle(self, *args, **opts):
        total = created_sources = created_links = 0
        for model in publishable_models().values():
            names = {f.name for f in model._meta.concrete_fields}
            if not names & {"source_url", "wikidata_id"}:
                continue  # nothing to link; skips the large regulator catalogue tables
            for record in model.objects.iterator(chunk_size=500):
                if not pipeline.has_source_evidence(record):
                    continue
                total += 1
                if opts["dry_run"]:
                    continue
                res = pipeline.prepare(record)
                created_sources += res["created_sources"]
                created_links += res["created_links"]
        merged = 0 if opts["dry_run"] else linking.dedupe_sources()["merged"]
        self.stdout.write(
            f"{total} records with source evidence; {created_sources} sources and "
            f"{created_links} links created; {merged} duplicate sources merged. "
            "Run the review-pipeline task to assess them."
        )
