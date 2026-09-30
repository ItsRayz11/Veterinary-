"""Development-only catalogue with obviously fictional names. Never verified, never clinical."""

from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.companies.models import Company
from apps.countries.models import Country
from apps.pharma.models import (
    DosageForm,
    Generic,
    Ingredient,
    Product,
    ProductIngredient,
    ProductPack,
    ProductRegistration,
)
from apps.units.models import Unit


class Command(BaseCommand):
    help = "Load fictional DEV products (Generic -> many brands -> companies) to exercise the UI."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_reference")
        pk = Country.objects.get(iso2="PK")
        dev = {"is_development_data": True}
        ingredient, _ = Ingredient.objects.get_or_create(name="Enrofloxacin")
        generic, _ = Generic.objects.get_or_create(name="Enrofloxacin", defaults=dev)
        generic.ingredients.add(ingredient)
        mg, ml = Unit.objects.get(code="mg"), Unit.objects.get(code="mL")
        inj = DosageForm.objects.get(slug="injection")
        for i, company_name in enumerate(["DEV Pharma Alpha", "DEV Pharma Beta"], start=1):
            company, _ = Company.objects.get_or_create(
                country=pk, name=company_name, defaults={"is_manufacturer": True, **dev}
            )
            product, _ = Product.objects.get_or_create(
                manufacturer=company,
                normalized_brand_name=f"dev enro {i}",
                defaults={"brand_name": f"DEV-Enro {i}", "generic": generic, **dev},
            )
            ProductIngredient.objects.get_or_create(
                product=product,
                ingredient=ingredient,
                defaults={"strength_value": Decimal("100"), "strength_unit": mg, "per_unit": ml},
            )
            ProductPack.objects.get_or_create(
                product=product,
                dosage_form=inj,
                pack_size_value=Decimal("100"),
                pack_size_unit=ml,
            )
            ProductRegistration.objects.get_or_create(
                country=pk,
                registration_number=f"DEV-{i:04d}",
                defaults={"product": product, **dev},
            )
        self.stdout.write(self.style.SUCCESS("Development catalogue loaded (NOT verified)."))
