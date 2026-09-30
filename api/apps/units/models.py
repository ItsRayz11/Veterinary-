from decimal import Decimal

from django.db import models


class Dimension(models.TextChoices):
    MASS = "mass"
    VOLUME = "volume"
    CONCENTRATION = "concentration"  # mass per volume
    DOSE_RATE = "dose_rate"  # mass per body weight
    BODY_WEIGHT = "body_weight"
    TIME = "time"
    PERCENT = "percent"
    ACTIVITY = "activity"  # IU
    COUNT = "count"  # tablets, doses


class Unit(models.Model):
    """Canonical unit. Every clinical or price quantity references a Unit row, never free text."""

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=64)
    dimension = models.CharField(max_length=16, choices=Dimension.choices)
    to_base = models.DecimalField(
        max_digits=30,
        decimal_places=15,
        default=Decimal(1),
        help_text="Multiply a value in this unit by this to get the dimension's base unit.",
    )

    class Meta:
        ordering = ["dimension", "code"]

    def __str__(self):
        return self.code

    def convert(self, value: Decimal, to: "Unit") -> Decimal:
        if self.dimension != to.dimension:
            raise ValueError(f"Cannot convert {self.code} ({self.dimension}) to {to.code}")
        return Decimal(value) * self.to_base / to.to_base
