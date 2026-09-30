from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core import reference_data as ref
from apps.countries.models import Country
from apps.pharma.models import DosageForm
from apps.species.models import Species
from apps.units.models import Unit


class Command(BaseCommand):
    help = "Idempotently load non-clinical reference data (countries, species, units, forms)."

    @transaction.atomic
    def handle(self, *args, **options):
        for iso2, name, cur, reg, order in ref.COUNTRIES:
            Country.objects.update_or_create(
                iso2=iso2,
                defaults={
                    "name": name,
                    "slug": name.lower().replace(" ", "-"),
                    "currency_code": cur,
                    "regulator_name": reg,
                    "sort_order": order,
                },
            )
        for order, (slug, name, parent, food) in enumerate(ref.SPECIES, start=1):
            Species.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "parent": Species.objects.get(slug=parent) if parent else None,
                    "is_food_producing": food,
                    "sort_order": order,
                },
            )
        for code, name, dim, factor in ref.UNITS:
            Unit.objects.update_or_create(
                code=code, defaults={"name": name, "dimension": dim, "to_base": Decimal(factor)}
            )
        for slug, name in ref.DOSAGE_FORMS:
            DosageForm.objects.update_or_create(slug=slug, defaults={"name": name})
        self.stdout.write(self.style.SUCCESS("Reference data loaded."))
