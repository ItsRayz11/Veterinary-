"""Helpers shared by the open-data adapters (UK VMD, Health Canada).

Like the DRAP cleaners, adapters only reshape what the source states into the standard import
format (docs/INGESTION.md). They never add, infer or correct clinical facts, and every record
the pipeline creates from them stays unreviewed and hidden until a veterinarian reviews it.
"""

import csv
import io
import json
import re
from dataclasses import dataclass, field

NAME_MAX = 200
GENERIC_MAX = 190
# One import file may hold at most services.MAX_ROWS rows and MAX_BYTES bytes; stay well below.
CHUNK_ROWS = 2000

COLUMNS = [
    "brand_name",
    "generic_name",
    "manufacturer",
    "registration_number",
    "registration_status",
    "composition",
    "ingredients",
    "target_species",
    "notes",
]
SPACE = re.compile(r"\s+")


@dataclass
class Cleaned:
    rows: list[dict]
    report: dict = field(default_factory=dict)
    # Registration numbers the source lists as expired (used to update existing registrations)
    expired_numbers: list[str] = field(default_factory=list)


def squash(value: str) -> str:
    return SPACE.sub(" ", value or "").strip()


def title_words(name: str) -> str:
    """Source text in capitals becomes 'Capital Case'; short all-caps words (HCl, USP) are kept."""
    return " ".join(w if (w.isupper() and len(w) <= 3) else w.capitalize() for w in name.split())


def join_generic(names: list[str]) -> str:
    """'A + B' within the column limit; a longer list keeps the first three and says so."""
    unique = list(dict.fromkeys(n for n in names if n))
    full = " + ".join(unique)
    if len(full) <= GENERIC_MAX:
        return full
    head = " + ".join(unique[:3])
    return f"{head} + {len(unique) - 3} more"[:GENERIC_MAX]


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                for k, v in row.items()
                if k in COLUMNS
            }
        )
    return out.getvalue()


def chunks(rows: list[dict], size: int = CHUNK_ROWS) -> list[list[dict]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)] or [[]]
