"""Text normalisation shared by matching, duplicate detection and slugs."""

import re
import unicodedata


def normalize_name(value: str) -> str:
    """Lowercase, strip accents/punctuation, collapse whitespace. Used for duplicate keys."""
    s = unicodedata.normalize("NFKD", value)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def unique_slug(model, base: str, instance=None, field: str = "slug") -> str:
    """A slug unique within `model`, always within the column's max_length (PostgreSQL enforces
    it; SQLite silently does not, which once hid a crash on long names)."""
    from django.utils.text import slugify

    limit = model._meta.get_field(field).max_length or 50
    root = (slugify(base)[: limit - 8] or "item").strip("-") or "item"  # room for "-<number>"
    slug, n = root, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(**{field: slug}).exists():
        suffix = f"-{n}"
        slug = f"{root[: limit - len(suffix)]}{suffix}"
        n += 1
    return slug
