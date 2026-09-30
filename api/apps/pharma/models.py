from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import PublishableModel, TimeStampedModel
from apps.core.text import normalize_name, unique_slug


class DrugClass(TimeStampedModel):
    """Pharmacological class tree, e.g. Antibacterials > Fluoroquinolones."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, editable=False)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["parent", "name"], name="uniq_class_name")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(DrugClass, self.name, self)
        super().save(*args, **kwargs)


class Ingredient(TimeStampedModel):
    """A single active substance. Combination products link several."""

    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, unique=True, editable=False)
    cas_number = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_name(self.name)
        super().save(*args, **kwargs)


class Generic(PublishableModel):
    """A generic medicine (one or more ingredients). Species-specific data lives elsewhere."""

    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, unique=True, editable=False)
    slug = models.SlugField(unique=True, editable=False)
    drug_class = models.ForeignKey(
        DrugClass, null=True, blank=True, on_delete=models.PROTECT, related_name="generics"
    )
    ingredients = models.ManyToManyField(Ingredient, related_name="generics")
    description = models.TextField(blank=True)
    mechanism = models.TextField(blank=True)

    history = HistoricalRecords()

    lists_unverified_imports = True

    class Meta(PublishableModel.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_name(self.name)
        if not self.slug:
            self.slug = unique_slug(Generic, self.name, self)
        super().save(*args, **kwargs)


class GenericSynonym(models.Model):
    """Alternate names/abbreviations/scientific names for search and matching."""

    generic = models.ForeignKey(Generic, on_delete=models.CASCADE, related_name="synonyms")
    synonym = models.CharField(max_length=200)
    normalized_synonym = models.CharField(max_length=200, unique=True, editable=False)

    def __str__(self):
        return self.synonym

    def save(self, *args, **kwargs):
        self.normalized_synonym = normalize_name(self.synonym)
        super().save(*args, **kwargs)


class DosageForm(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(PublishableModel):
    """A brand/product from one manufacturer. Prices attach to ProductPack, not here."""

    brand_name = models.CharField(max_length=200)
    normalized_brand_name = models.CharField(max_length=200, editable=False)
    slug = models.SlugField(unique=True, editable=False)
    generic = models.ForeignKey(Generic, on_delete=models.PROTECT, related_name="products")
    manufacturer = models.ForeignKey(
        "companies.Company", on_delete=models.PROTECT, related_name="manufactured_products"
    )
    marketing_holder = models.ForeignKey(
        "companies.Company",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="marketed_products",
    )
    category = models.CharField(max_length=100, blank=True)
    is_biologic = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    history = HistoricalRecords()

    lists_unverified_imports = True

    class Meta(PublishableModel.Meta):
        ordering = ["brand_name"]
        constraints = [
            *PublishableModel.Meta.constraints,
            models.UniqueConstraint(
                fields=["manufacturer", "normalized_brand_name"], name="uniq_product_brand"
            ),
        ]

    def __str__(self):
        return self.brand_name

    def save(self, *args, **kwargs):
        self.normalized_brand_name = normalize_name(self.brand_name)
        if not self.slug:
            self.slug = unique_slug(Product, f"{self.brand_name}", self)
        super().save(*args, **kwargs)


class ProductIngredient(models.Model):
    """Strength of one ingredient, e.g. 100 mg per 1 mL."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ingredients")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="+")
    strength_value = models.DecimalField(
        max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))]
    )
    strength_unit = models.ForeignKey("units.Unit", on_delete=models.PROTECT, related_name="+")
    per_value = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal(1))
    per_unit = models.ForeignKey(
        "units.Unit",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="mL, g, tablet... Empty when the strength is stated per unit dose.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "ingredient"], name="uniq_product_ingredient"
            ),
            models.CheckConstraint(
                condition=models.Q(strength_value__gt=0), name="strength_positive"
            ),
            models.CheckConstraint(condition=models.Q(per_value__gt=0), name="per_value_positive"),
        ]

    def __str__(self):
        return f"{self.ingredient} {self.strength_value}{self.strength_unit}"


class ProductPack(TimeStampedModel):
    """A sellable presentation: form x pack size. Prices attach here."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="packs")
    dosage_form = models.ForeignKey(DosageForm, on_delete=models.PROTECT, related_name="+")
    pack_size_value = models.DecimalField(max_digits=12, decimal_places=3)
    pack_size_unit = models.ForeignKey("units.Unit", on_delete=models.PROTECT, related_name="+")
    barcode = models.CharField(max_length=32, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "dosage_form", "pack_size_value", "pack_size_unit"],
                name="uniq_product_pack",
            ),
            models.CheckConstraint(condition=models.Q(pack_size_value__gt=0), name="pack_positive"),
        ]

    def __str__(self):
        return f"{self.product} {self.dosage_form} {self.pack_size_value}{self.pack_size_unit}"


class RegistrationStatus(models.TextChoices):
    REGISTERED = "registered", "Registered"
    EXPIRED = "expired", "Expired"
    SUSPENDED = "suspended", "Suspended"
    WITHDRAWN = "withdrawn", "Withdrawn"
    UNKNOWN = "unknown", "Unknown"


class ProductRegistration(PublishableModel):
    """Country availability/regulatory record for a product."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="registrations")
    country = models.ForeignKey(
        "countries.Country", on_delete=models.PROTECT, related_name="registrations"
    )
    registration_number = models.CharField(max_length=100)
    status = models.CharField(
        max_length=16, choices=RegistrationStatus.choices, default=RegistrationStatus.UNKNOWN
    )
    registered_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta(PublishableModel.Meta):
        constraints = [
            *PublishableModel.Meta.constraints,
            models.UniqueConstraint(
                fields=["country", "registration_number"], name="uniq_registration_number"
            ),
        ]

    def __str__(self):
        return f"{self.product} [{self.country.iso2} {self.registration_number}]"
