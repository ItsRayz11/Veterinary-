"""Undo an automated import. Dry run unless --apply is given.

    python manage.py rollback_import --source uk-vmd-pid --since 2026-11-05            # preview
    python manage.py rollback_import --source uk-vmd-pid --since 2026-11-05 --apply

Removes only records that (a) were created from a Source of that data source on/after --since and
(b) are still "Imported, not reviewed". Anything a reviewer has touched is kept and listed. Status
changes the sync made are put back to the value recorded in the audit log. For a full-database
restore use the Neon snapshot taken before the import (docs/ADMIN.md).
"""

from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.automation.models import DataSource
from apps.companies.models import Company
from apps.core.models import AuditLog, ReviewStatus
from apps.ingestion.models import ImportBatch
from apps.pharma.models import Generic, Product, ProductRegistration
from apps.sources.models import Source, SourceLink


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="DataSource slug")
        parser.add_argument("--since", required=True, help="YYYY-MM-DD (Source.accessed_date)")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        ds = DataSource.objects.filter(slug=opts["source"]).first()
        if ds is None:
            raise CommandError(f"No data source {opts['source']!r}.")
        try:
            since = date.fromisoformat(opts["since"])
        except ValueError as exc:
            raise CommandError("--since must be YYYY-MM-DD") from exc
        sources = Source.objects.filter(
            title__startswith=ds.name, accessed_date__gte=since, publisher=ds.publisher
        )
        pks = list(sources.values_list("pk", flat=True))
        self.stdout.write(f"{len(pks)} source record(s) from {ds.name} since {since}.")

        def linked(model):
            ct = ContentType.objects.get_for_model(model)
            ids = SourceLink.objects.filter(source_id__in=pks, content_type=ct).values_list(
                "object_id", flat=True
            )
            return model.objects.filter(pk__in=ids)

        unrev = ReviewStatus.IMPORTED_UNVERIFIED
        regs = linked(ProductRegistration)
        products = linked(Product)
        kept = (
            regs.exclude(review_status=unrev).count()
            + products.exclude(review_status=unrev).count()
        )
        regs_del = regs.filter(review_status=unrev)
        products_del = products.filter(review_status=unrev).exclude(
            registrations__in=ProductRegistration.objects.exclude(review_status=unrev)
        )
        status_undo = AuditLog.objects.filter(
            action="registration_status_changed", reason__startswith=f"Source: {ds.name}"
        )
        self.stdout.write(
            f"Would remove {regs_del.count()} registrations, {products_del.count()} products; "
            f"restore {status_undo.count()} status changes; keep {kept} reviewed record(s)."
        )
        if not opts["apply"]:
            self.stdout.write("Dry run: nothing changed. Add --apply to proceed.")
            return
        with transaction.atomic():
            for log in status_undo.order_by("-at"):
                reg = ProductRegistration.objects.filter(pk=log.object_id).first()
                if reg and log.before and reg.review_status == unrev:
                    reg.status = log.before["status"]
                    reg.save(update_fields=["status", "updated_at"])
            regs_del.delete()
            gen_ids = set(products_del.values_list("generic_id", flat=True))
            co_ids = set(products_del.values_list("manufacturer_id", flat=True))
            products_del.delete()
            Generic.objects.filter(
                pk__in=gen_ids, review_status=unrev, products__isnull=True
            ).delete()
            Company.objects.filter(
                pk__in=co_ids,
                review_status=unrev,
                manufactured_products__isnull=True,
                marketed_products__isnull=True,
            ).delete()
            AuditLog.objects.create(
                action="import_rolled_back",
                object_type="automation.DataSource",
                object_id=str(ds.pk),
                after={"since": str(since)},
                reason=f"Rollback of {ds.name}",
            )
            ImportBatch.objects.filter(
                source_id__in=pks
            ).delete()  # allow the file to be staged again
            ds.imported_fingerprint = ""
            ds.last_imported_at = None
            ds.update_available = True
            ds.save()
        self.stdout.write(self.style.SUCCESS("Rolled back."))
