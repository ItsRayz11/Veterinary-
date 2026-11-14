"""Health Canada Drug Product Database, bulk "all files" extract (zip of CSV text files).

Preferred ingestion path: the official bulk ZIPs on www.canada.ca (allfiles.zip = marketed;
allfiles_ap / _dr / _ia = approved / dormant / cancelled), not repeated calls to the DPD API.
Publisher terms: the extract page defers to the DPD "Terms and Conditions"; whether the OGL-Canada
applies to this dataset is NOT yet confirmed (see docs/HEALTH_CANADA_DPD.md). The source stays
import-disabled until a person records that confirmation.

Only products whose CLASS is "Veterinary" are used. All files are joined on DRUG_CODE:

    drug.txt    0 DRUG_CODE, 2 CLASS, 3 DRUG_IDENTIFICATION_NUMBER (DIN), 4 BRAND_NAME,
                9 LAST_UPDATE_DATE
    comp.txt    0 DRUG_CODE, 3 COMPANY_NAME
    ingred.txt  0 DRUG_CODE, 2 INGREDIENT, 4 STRENGTH, 5 STRENGTH_UNIT
    status.txt  0 DRUG_CODE, 1 CURRENT_STATUS_FLAG, 2 STATUS, 3 HISTORY_DATE
    vet.txt     0 DRUG_CODE, 1 VET_SPECIES, 2 VET_SUB_SPECIES      (optional)
    route.txt   0 DRUG_CODE, 2 ROUTE_OF_ADMINISTRATION             (optional)
    form.txt    0 DRUG_CODE, 2 PHARMACEUTICAL_FORM                 (optional)

The files are documented as comma separated, double-quoted, and may or may not carry a header
row; a first row starting with DRUG_CODE is skipped. Nothing is parsed or inferred: strengths,
species, routes and statuses are kept as the source's own text. The original status string,
source DRUG_CODE and last-updated dates are preserved in `notes` for the reviewer, and every row
is staged unreviewed (hidden) by the pipeline. No dose, withdrawal period or indication is read.
"""

import csv
import io
import zipfile
from collections import Counter, defaultdict

from .common import NAME_MAX, Cleaned, join_generic, squash, title_words

STATUS = {
    "MARKETED": "registered",
    "APPROVED": "registered",
    "DORMANT": "suspended",
    "CANCELLED PRE MARKET": "withdrawn",
    "CANCELLED POST MARKET": "withdrawn",
    "CANCELLED (UNRETURNED ANNUAL)": "withdrawn",
    "CANCELLED (SAFETY ISSUE)": "withdrawn",
    "AUTHORIZATION BY INTERIM ORDER EXPIRED": "withdrawn",
    "AUTHORIZATION BY INTERIM ORDER REVOKED": "withdrawn",
}
MAX_UNCOMPRESSED = 60_000_000
MAX_ARCHIVE_MEMBERS = 200
REQUIRED = ("drug.txt", "status.txt", "comp.txt", "ingred.txt")
OPTIONAL = ("vet.txt", "route.txt", "form.txt")
NOTES_MAX = 900
SOURCE_LABEL = "Health Canada Drug Product Database"


class ExtractError(ValueError):
    """The archive is not a usable DPD extract (missing file, wrong layout)."""


def _member(archive: zipfile.ZipFile, base: str) -> str | None:
    """Archive member for `base` ('drug.txt'); also accepts drug_ap.txt / _dr / _ia variants."""
    stem = base.removesuffix(".txt")
    names = archive.namelist()
    for name in names:
        short = name.rsplit("/", 1)[-1].lower()
        if short == base or (short.startswith(stem + "_") and short.endswith(".txt")):
            if short == base or short[len(stem) + 1 : -4] in ("ap", "dr", "ia"):
                return name
    return None


def _read(archive: zipfile.ZipFile, base: str, *, required: bool) -> list[list[str]]:
    name = _member(archive, base)
    if name is None:
        if required:
            raise ExtractError(f"{base} is missing from the extract")
        return []
    info = archive.getinfo(name)
    if info.file_size > MAX_UNCOMPRESSED:
        raise ExtractError(f"{name} is unexpectedly large")
    text = archive.read(name).decode("utf-8-sig", errors="replace")
    rows = [r for r in csv.reader(io.StringIO(text)) if r]
    if rows and rows[0][0].strip().upper() == "DRUG_CODE":
        rows = rows[1:]
    return rows


def _cell(row: list[str], index: int) -> str:
    return squash(row[index]) if len(row) > index else ""


def _open(data: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ExtractError("the download is not a zip archive") from exc
    if len(archive.namelist()) > MAX_ARCHIVE_MEMBERS:
        raise ExtractError("the archive holds an unexpected number of files")
    return archive


def _species_label(species: str, sub: str) -> str:
    species, sub = title_words(species), title_words(sub)
    return f"{species} ({sub})" if sub and sub.lower() != species.lower() else species


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


def clean_extract(data: bytes) -> Cleaned:
    archive = _open(data)
    drug_rows = _read(archive, "drug.txt", required=True)
    if not any(_cell(r, 0).isdigit() for r in drug_rows[:50]):
        raise ExtractError("drug.txt does not look like a DPD extract (no DRUG_CODE column)")
    status_rows = _read(archive, "status.txt", required=True)
    comp_rows = _read(archive, "comp.txt", required=True)
    ingred_rows = _read(archive, "ingred.txt", required=True)
    vet_rows = _read(archive, "vet.txt", required=False)
    route_rows = _read(archive, "route.txt", required=False)
    form_rows = _read(archive, "form.txt", required=False)

    report: Counter = Counter()
    drugs: dict[str, list[str]] = {}
    for r in drug_rows:
        code = _cell(r, 0)
        if len(r) <= 4 or _cell(r, 2) != "Veterinary":
            continue
        if code in drugs:
            report["skipped_duplicate_drug_code"] += 1
            continue
        drugs[code] = r

    status: dict[str, tuple[str, str]] = {}
    for r in status_rows:
        code = _cell(r, 0)
        if code in drugs and _cell(r, 1) == "Y" and code not in status:
            status[code] = (_cell(r, 2).upper(), _cell(r, 3))
    company: dict[str, str] = {}
    for r in comp_rows:
        code = _cell(r, 0)
        if code in drugs and code not in company and _cell(r, 3):
            company[code] = _cell(r, 3)
    ingredients: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in ingred_rows:
        if _cell(r, 0) in drugs and _cell(r, 2):
            ingredients[_cell(r, 0)].append(
                (title_words(_cell(r, 2)), squash(f"{_cell(r, 4)} {_cell(r, 5)}"))
            )
    species: dict[str, list[str]] = defaultdict(list)
    for r in vet_rows:
        if _cell(r, 0) in drugs and _cell(r, 1):
            species[_cell(r, 0)].append(_species_label(_cell(r, 1), _cell(r, 2)))
    routes: dict[str, list[str]] = defaultdict(list)
    for r in route_rows:
        if _cell(r, 0) in drugs and _cell(r, 2):
            routes[_cell(r, 0)].append(title_words(_cell(r, 2)))
    forms: dict[str, list[str]] = defaultdict(list)
    for r in form_rows:
        if _cell(r, 0) in drugs and _cell(r, 2):
            forms[_cell(r, 0)].append(title_words(_cell(r, 2)))

    rows: list[dict] = []
    seen_din: set[str] = set()
    for code, drug in drugs.items():
        report["veterinary_products"] += 1
        brand, din = title_words(_cell(drug, 4)), _cell(drug, 3)
        names = [n for n, _ in ingredients.get(code, [])]
        manufacturer = company.get(code, "")
        if not (brand and names and manufacturer and din):
            report["skipped_incomplete"] += 1
            continue
        if len(brand) > NAME_MAX:
            report["skipped_name_too_long"] += 1
            continue
        if din in seen_din:
            report["skipped_duplicate_din"] += 1
            continue
        seen_din.add(din)
        current, status_date = status.get(code, ("", ""))
        if current and current not in STATUS:
            report["unmapped_status"] += 1
        updated = _cell(drug, 9)
        parts = [
            f"Health Canada status: {current.title() or 'not stated'}"
            + (f" (since {status_date})" if status_date else "")
            + ".",
            f"Source: {SOURCE_LABEL}, DRUG_CODE {code}"
            + (f", record updated {updated}" if updated else "")
            + ".",
        ]
        if forms.get(code):
            parts.append("Form: " + ", ".join(_unique(forms[code])) + ".")
        if routes.get(code):
            parts.append("Route: " + ", ".join(_unique(routes[code])) + ".")
        rows.append(
            {
                "brand_name": brand,
                "generic_name": join_generic(names),
                "manufacturer": title_words(manufacturer),
                "registration_number": din,
                "registration_status": STATUS.get(current, "unknown"),
                "composition": "; ".join(f"{n} {s}".strip() for n, s in ingredients[code]),
                "target_species": [{"label": x} for x in _unique(species.get(code, []))],
                "notes": " ".join(parts)[:NOTES_MAX],
            }
        )
        report["rows"] += 1
        if not species.get(code):
            report["rows_without_species"] += 1
    if report["veterinary_products"] == 0:
        raise ExtractError("no veterinary products found; the CLASS column layout may have changed")
    return Cleaned(rows, dict(report))
