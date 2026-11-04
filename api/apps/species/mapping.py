"""Exact mapping from a regulator's target-species wording to our species table.

Only unambiguous names are mapped; everything else stays as the regulator's own label with no
species link. Never widen this to "similar" animals: an authorisation for pigs says nothing about
other species.
"""

import re

_MAP = {
    "dog": "dog", "dogs": "dog",
    "cat": "cat", "cats": "cat",
    "cattle": "cattle",
    "pig": "swine", "pigs": "swine",
    "horse": "horse", "horses": "horse",
    "sheep": "sheep",
    "goat": "goat", "goats": "goat",
    "chicken": "poultry", "chickens": "poultry", "poultry": "poultry",
    "turkey": "turkey", "turkeys": "turkey",
    "rabbit": "rabbit", "rabbits": "rabbit",
    "buffalo": "buffalo",
    "camel": "camel", "camels": "camel",
    "fish": "fish", "atlantic salmon": "fish", "salmon": "fish", "trout": "fish",
    "ornamental fish": "fish",
}  # fmt: skip


def species_slug(label: str) -> str | None:
    key = re.sub(r"\s+", " ", label.strip().lower())
    if key.startswith("trout - "):
        key = "trout"
    return _MAP.get(key)


def split_labels(text: str) -> list[str]:
    """'Cattle, Pigs' -> ['Cattle', 'Pigs'] (duplicates removed, order kept)."""
    seen = {}
    for part in text.split(","):
        part = re.sub(r"\s+", " ", part).strip()
        if part:
            seen.setdefault(part.lower(), part)
    return list(seen.values())
