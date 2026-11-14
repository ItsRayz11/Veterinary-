from django.db import models


class SearchMiss(models.Model):
    """A search that found nothing. Only the normalised text and a counter are stored: no user,
    no address, no session, so it holds nothing personal. It tells staff which data to import."""

    query = models.CharField(max_length=100, unique=True, help_text="Normalised search text")
    example = models.CharField(max_length=100, help_text="One spelling a visitor actually typed")
    count = models.PositiveIntegerField(default=1)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    resolved = models.BooleanField(default=False, help_text="Data was added or it is not wanted")

    class Meta:
        ordering = ["-count", "-last_seen"]

    def __str__(self):
        return f"{self.query} x{self.count}"
