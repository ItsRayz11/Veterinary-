"""Check external data sources and import the ones that changed.

    python manage.py sync_data_sources                 # check all, import changed importable ones
    python manage.py sync_data_sources --check-only    # reachability / change check only
    python manage.py sync_data_sources --source uk-vmd-pid --force

Importing needs an importer, `import_enabled` and confirmed terms (Django admin). Every imported
record is created unreviewed (never public) until a veterinarian reviewer promotes it.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.automation import datasources
from apps.automation.models import DataSource


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("--source", help="slug of one source")
        parser.add_argument("--check-only", action="store_true")
        parser.add_argument(
            "--force", action="store_true", help="import even if the file has not changed"
        )

    def handle(self, *args, **opts):
        sources = DataSource.objects.all()
        if opts["source"]:
            sources = sources.filter(slug=opts["source"])
            if not sources:
                raise CommandError(f"No data source {opts['source']!r}.")
        cache: dict = {}
        for source in sources.filter(enabled=True):
            datasources.check_source(source, cache)
            state = "ok" if source.last_ok else (source.last_error or "unreachable")
            flag = " [update available]" if source.update_available else ""
            self.stdout.write(f"{source.slug}: {state}{flag}")
        if opts["check_only"]:
            return
        wanted = (
            [s for s in sources if s.importer and s.import_enabled]
            if opts["force"]
            else [s for s in datasources.due_for_import() if s in sources]
        )
        failures = 0
        for source in wanted:
            self.stdout.write(f"Importing {source.slug} ...")
            try:
                result = datasources.sync_source(source, log=self.stdout.write)
            except datasources.SyncError as exc:
                failures += 1
                source.last_import_result = f"failed: {exc}"[:300]
                source.save(update_fields=["last_import_result", "updated_at"])
                self.stderr.write(self.style.ERROR(f"  {source.slug}: {exc}"))
                continue
            self.stdout.write(self.style.SUCCESS(f"  {source.slug}: {result}"))
        if failures:
            raise CommandError(f"{failures} import(s) failed.")
