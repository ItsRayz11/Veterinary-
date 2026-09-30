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
    from django.utils.text import slugify

    root = slugify(base)[:150] or "item"
    slug, n = root, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(**{field: slug}).exists():
        slug = f"{root}-{n}"
        n += 1
    return slug
