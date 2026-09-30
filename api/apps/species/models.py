from django.db import models

from apps.core.models import TimeStampedModel


class Species(TimeStampedModel):
    """A species or production class (e.g. broiler). Clinical data never crosses species."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_food_producing = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "species"

    def __str__(self):
        return self.name
