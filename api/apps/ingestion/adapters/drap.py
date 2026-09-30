"""Cleaners for the two public DRAP (Pakistan) veterinary lists.

Both files list *applications* for registration, not registrations, so nothing produced here ever
carries a registration number or a "registered" status. Each cleaner turns a source file into rows
of the standard import format (see docs/INGESTION.md); the import pipeline then stages, matches and
holds every record for human review. Cleaning only reshapes what the source states: it does not
add, infer or correct clinical facts. Anything that cannot be parsed unambiguously is left out of
the structured fields and kept as the source's own text.
"""

import csv
import hashlib
import html
import io
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field

TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")
NAME_MAX = 200
GENERIC_MAX = 190

# Source spellings of units -> our unit codes. Anything else is left unstructured.
UNIT_CODES = {
    "mg": "mg",
    "gm": "g",
    "g": "g",
    "gram": "g",
    "kg": "kg",
    "mcg": "mcg",
    "µg": "mcg",  # micro sign
    "μg": "mcg",  # Greek mu
    "iu": "IU",
    "i.u": "IU",
    "%": "%",
    "ml": "mL",
    "l": "L",
}
MEGA_UNITS = {"miu": ("IU", 1_000_000)}  # million IU

# Words that identify a dosage form in a brand name -> DosageForm slug (reference data).
FORM_WORDS = [
    ("water soluble powder", "water-soluble-powder"),
    ("intramammary", "intramammary"),
    ("oral liquid", "oral-solution"),
    ("oral solution", "oral-solution"),
    ("injection", "injection"),
    ("premix", "premix"),
    ("bolus", "bolus"),
    ("boli", "bolus"),
    ("tablet", "tablet"),
    ("suspension", "suspension"),
    ("pour-on", "pour-on"),
    ("pour on", "pour-on"),
    ("ointment", "ointment"),
]

SALTS = [
    (re.compile(r"\bhcl\b\.?", re.I), "Hydrochloride"),
    (re.compile(r"\bhydrochloride\b", re.I), "Hydrochloride"),
]
ASIDE = re.compile(r"\s+as\s+(?:base|anhydrous|active|free base)\b.*$", re.I)


@dataclass
class Cleaned:
    rows: list[dict] = field(default_factory=list)
    report: dict = field(default_factory=dict)
    checksum: str = ""


def _text(value: str) -> str:
    """Strip HTML remnants and entities, collapse whitespace."""
    return SPACE.sub(" ", html.unescape(TAG.sub("", value or ""))).strip()


def _lines(value: str) -> list[str]:
    return [
        line for line in (_text(x) for x in re.split(r"[\r\n]+", TAG.sub("", value or ""))) if line
    ]


def clean_company(raw: str) -> tuple[str, str]:
    """('Mallard Pharmaceuticals Pvt Ltd', 'address lines...') from the source's name block."""
    lines = _lines(raw)
    if not lines:
        return "", ""
    name = re.sub(r"^m/?s\.?\s+", "", lines[0], flags=re.I).strip(" .,")
    return name[:NAME_MAX], " ".join(lines[1:])


def clean_ingredient_name(name: str) -> str:
    name = ASIDE.sub("", _text(name)).strip(" .,:-")
    for pattern, replacement in SALTS:
        name = pattern.sub(replacement, name)
    return " ".join(w if w.isupper() and len(w) <= 3 else w.capitalize() for w in name.split())


def parse_strength(value: str) -> tuple[str, str] | None:
    """('31.5', 'mg') from '31.5mg', already in our unit codes; None when not unambiguous."""
    m = re.match(r"^\s*(\d[\d,]*(?:\.\d+)?)\s*([^\d\s].*?)\s*\.?\s*$", _text(value))
    if not m:
        return None
    number, unit = m.group(1).replace(",", ""), m.group(2).strip().lower()
    if unit in MEGA_UNITS:
        code, factor = MEGA_UNITS[unit]
        return (format(float(number) * factor, "f").rstrip("0").rstrip("."), code)
    code = UNIT_CODES.get(unit)
    return (number, code) if code else None


def parse_composition(text: str) -> dict:
    """Split a composition block into per-unit basis and ingredients.

    Returns {"per_value", "per_unit", "ingredients": [{name, value, unit}], "unparsed": [...]}.
    Ingredients whose strength cannot be read unambiguously are listed in "unparsed" (by name) and
    are not given a structured strength.
    """
    per_value, per_unit = "1", None
    ingredients, unparsed = [], []
    for line in _lines(text):
        header = re.match(
            r"^each\s+(\d+(?:\.\d+)?)?\s*(ml|gm|gram|g|kg|l)\b[^:]*contains?\s*:?\s*$", line, re.I
        )
        if header:
            per_value = header.group(1) or "1"
            per_unit = UNIT_CODES.get(header.group(2).lower())
            continue
        parts = re.split(r"\s*(?:…|\.{2,})\s*", line, maxsplit=1)
        if len(parts) != 2 or not parts[0]:
            if not re.match(r"^(each|contains?)\b", line, re.I):
                unparsed.append(line)
            continue
        name, strength = clean_ingredient_name(parts[0]), parse_strength(parts[1])
        if not name:
            continue
        if strength:
            ingredients.append({"name": name, "value": strength[0], "unit": strength[1]})
        else:
            unparsed.append(name)
    return {
        "per_value": per_value,
        "per_unit": per_unit,
        "ingredients": ingredients,
        "unparsed": unparsed,
    }


def generic_name_for(names: list[str]) -> str:
    """Stable name for a combination: unique names, sorted, joined with ' + '.

    Very long combinations are shortened with a hash of the full list, so two different mixes
    never collapse into one generic."""
    unique = sorted({n for n in names if n}, key=str.lower)
    full = " + ".join(unique)
    if len(full) <= GENERIC_MAX:
        return full
    digest = hashlib.sha1(full.encode("utf-8"), usedforsecurity=False).hexdigest()[:6]
    head = " + ".join(unique[:3])
    return f"{head[: GENERIC_MAX - 40]} + {len(unique) - 3} more [{digest}]"


def split_pack(brand: str) -> tuple[str, dict | None]:
    """('Ivermall 3.15% Injection', {'size': '50', 'unit': 'mL', 'form': 'injection'}) or the brand
    unchanged when it has no trailing millilitre/litre size."""
    brand = _text(brand)
    m = re.search(r"\s+(\d+(?:\.\d+)?)\s*(ml|l)\s*$", brand, re.I)
    if not m:
        return brand, None
    base = brand[: m.start()].strip()
    pack = {"size": m.group(1), "unit": UNIT_CODES[m.group(2).lower()]}
    form = form_slug(base)
    if form:
        pack["form"] = form
    return base, pack


def form_slug(text: str) -> str | None:
    low = text.lower()
    for word, slug in FORM_WORDS:
        if word in low:
            return slug
    return None


SOURCE_NOTE = (
    "Listed in DRAP's public list of applications for registration of veterinary drugs. "
    "This is an application, not a registration."
)


def clean_vet_applications(text: str) -> Cleaned:
    """DRAP 'List of Vet Applications' CSV -> standard rows (one per company + product name)."""
    reader = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    body = [r for r in reader[1:] if len(r) >= 5 and _text(r[2])]
    grouped: dict[tuple[str, str], dict] = {}
    report = defaultdict(int)
    report["source_rows"] = len(body)
    for r in body:
        company, address = clean_company(r[1])
        brand, pack = split_pack(r[2])
        comp = parse_composition(r[3])
        names = [i["name"] for i in comp["ingredients"]] + comp["unparsed"]
        if not company or not brand or not names:
            report["skipped_incomplete"] += 1
            continue
        key = (company.lower(), brand.lower())
        form_type = re.match(r"\s*(Form-\w+)", _text(r[4]))
        application = _text(r[4])
        entry = grouped.get(key)
        if entry is None:
            per = {"per_value": comp["per_value"], "per_unit": comp["per_unit"]}
            entry = grouped[key] = {
                "brand_name": brand[:NAME_MAX],
                "generic_name": generic_name_for(names),
                "manufacturer": company,
                "manufacturer_address": address,
                "registration_number": "",
                "composition": " | ".join(_lines(r[3])),
                "ingredients": [{**i, **per} for i in comp["ingredients"]],
                "packs": [],
                "notes": SOURCE_NOTE,
                "applications": [],
                "is_biologic": "false",
                "company_role": "manufacturer",
            }
            if comp["unparsed"]:
                report["with_unparsed_ingredients"] += 1
        elif entry["composition"] != " | ".join(_lines(r[3])):
            report["variants_with_different_composition_kept_first"] += 1
        if pack and pack not in entry["packs"]:
            entry["packs"].append(pack)
        entry["applications"].append(application)
        if form_type:
            report[f"form_{form_type.group(1)}"] += 1
    rows = []
    for e in grouped.values():
        e["notes"] += " Applications: " + "; ".join(e.pop("applications"))[:600]
        rows.append(e)
    report["products"] = len(rows)
    report["manufacturers"] = len({r["manufacturer"].lower() for r in rows})
    report["with_structured_ingredients"] = sum(1 for r in rows if r["ingredients"])
    report["with_packs"] = sum(1 for r in rows if r["packs"])
    return Cleaned(rows, dict(report), hashlib.sha256(text.encode("utf-8")).hexdigest())


BIOLOGIC_NOTE = (
    "Listed in DRAP's public list of applications for registration of veterinary biologicals. "
    "This is an application, not a registration."
)


def clean_vet_biologicals(text: str) -> Cleaned:
    """DRAP 'Applications for registration of Veterinary Biologicals' CSV -> standard rows.

    The applicant (a company in the import country) is recorded as the company; the foreign
    manufacturer named in the source is kept in the product's notes, because the catalogue only
    holds companies in a country it knows. The antigen is not classified here, so each product goes
    under one clearly-named placeholder generic that a reviewer replaces."""
    reader = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    header = [_text(h).lower() for h in reader[0]]

    def col(name):
        return header.index(name)

    ci = {
        k: col(k)
        for k in (
            "applicant",
            "applied product",
            "application date",
            "manufacturer",
            "origin",
            "remarks",
        )
    }
    grouped, report = {}, defaultdict(int)
    for r in reader[1:]:
        if len(r) < len(header) or not _text(r[ci["applied product"]]):
            continue
        report["source_rows"] += 1
        applicant, _ = clean_company(re.sub(r",\s*[A-Za-z ]+$", "", r[ci["applicant"]]))
        product = _text(r[ci["applied product"]])[:NAME_MAX]
        if not applicant:
            report["skipped_incomplete"] += 1
            continue
        key = (applicant.lower(), product.lower())
        if key in grouped:
            report["duplicates_merged"] += 1
            continue
        stated = _text(r[ci["manufacturer"]])
        note = (
            f"{BIOLOGIC_NOTE} Applicant: {_text(r[ci['applicant']])}. "
            f"Manufacturer stated: {stated}. Origin: {_text(r[ci['origin']])}. "
            f"Application date: {_text(r[ci['application date']])}. "
            f"Status remark: {_text(r[ci['remarks']])}"
        )
        grouped[key] = {
            "brand_name": product,
            "generic_name": "Veterinary biological (antigen not yet classified)",
            "manufacturer": applicant,
            "manufacturer_address": "",
            "registration_number": "",
            "composition": "",
            "ingredients": [],
            "packs": [],
            "notes": note[:2000],
            "is_biologic": "true",
            "company_role": "importer",
        }
    rows = list(grouped.values())
    report["products"] = len(rows)
    report["companies"] = len({r["manufacturer"].lower() for r in rows})
    return Cleaned(rows, dict(report), hashlib.sha256(text.encode("utf-8")).hexdigest())


STANDARD_COLUMNS = [
    "brand_name",
    "generic_name",
    "manufacturer",
    "manufacturer_address",
    "registration_number",
    "composition",
    "ingredients",
    "packs",
    "notes",
    "is_biologic",
    "company_role",
]


def to_csv(rows: list[dict]) -> str:
    """Standard import CSV; nested values are JSON strings inside their cells."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=STANDARD_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                for k, v in row.items()
                if k in STANDARD_COLUMNS
            }
        )
    return out.getvalue()
