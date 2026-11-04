"""Idempotent first-load of public reference data. Safe to run on every production deploy.

Loads countries/species/units/forms, the drug-class tree and filing of single-substance generics,
and (unless --skip-universities) imports veterinary schools as *unreviewed* records. Network
failures in the university step are reported but never fail the deploy.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.pharma import taxonomy
from apps.pharma.models import DrugClass, Generic


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("--skip-universities", action="store_true")

    def handle(self, *args, **opts):
        call_command("seed_reference")
        self.load_classes()
        from apps.accounts import roles

        roles.ensure_groups()
        if not opts["skip_universities"]:
            try:
                call_command("import_universities")
            except Exception as exc:  # noqa: BLE001 - a flaky source must not block a deploy
                self.stderr.write(f"University import failed (will retry next deploy): {exc}")
        self.stdout.write(self.style.SUCCESS("Public data bootstrap finished."))

    @transaction.atomic
    def load_classes(self):
        nodes: dict[str, DrugClass] = {}
        for parent, name in taxonomy.CLASS_TREE:
            node, _ = DrugClass.objects.get_or_create(
                name=name, parent=nodes[parent] if parent else None
            )
            nodes[name] = node
        filed = 0
        for g in Generic.objects.filter(drug_class__isnull=True).only("id", "name"):
            cls = taxonomy.class_for(g.name)
            if cls:
                Generic.objects.filter(pk=g.pk).update(drug_class=nodes[cls])
                filed += 1
        self.stdout.write(f"Drug classes: {len(nodes)} in tree, {filed} generics filed.")
