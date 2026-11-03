"""Health Canada Drug Product Database, "all files" extract (zip of header-less CSV files).

Source: https://open.canada.ca/data/en/dataset/bf55e42a-63cb-4556-bfd8-44f26e5a36fe
(Open Government Licence - Canada; confirm on the dataset page). Only products whose class is
"Veterinary" are used. The Drug Identification Number (DIN) is the registration number; the
current status maps to registered (marketed or approved), suspended (dormant) or withdrawn
(cancelled). Ingredient strengths are kept as the source's text in `composition`, never parsed.

Column positions follow the DPD read-me: drug.txt (0 drug code, 2 class, 3 DIN, 4 brand name),
comp.txt (0 drug code, 3 company name), ingred.txt (0 drug code, 2 ingredient, 4 strength,
5 strength unit), status.txt (0 drug code, 1 current flag Y/N, 2 status).
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
}
MAX_UNCOMPRESSED = 60_000_000


def _read(archive: zipfile.ZipFile, name: str) -> list[list[str]]:
    info = archive.getinfo(name)
    if info.file_size > MAX_UNCOMPRESSED:
        raise ValueError(f"{name} is unexpectedly large")
    text = archive.read(name).decode("utf-8", errors="replace")
    return list(csv.reader(io.StringIO(text)))


def clean_extract(data: bytes) -> Cleaned:
    archive = zipfile.ZipFile(io.BytesIO(data))
    drugs = {r[0]: r for r in _read(archive, "drug.txt") if len(r) > 4 and r[2] == "Veterinary"}
    status = {
        r[0]: r[2].strip().upper()
        for r in _read(archive, "status.txt")
        if len(r) > 2 and r[0] in drugs and r[1] == "Y"
    }
    company = {}
    for r in _read(archive, "comp.txt"):
        if len(r) > 3 and r[0] in drugs and r[0] not in company:
            company[r[0]] = squash(r[3])
    ingredients: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in _read(archive, "ingred.txt"):
        if len(r) > 5 and r[0] in drugs and squash(r[2]):
            ingredients[r[0]].append((title_words(squash(r[2])), squash(f"{r[4]} {r[5]}")))

    report: Counter = Counter()
    rows = []
    for code, drug in drugs.items():
        report["veterinary_products"] += 1
        brand, din = title_words(squash(drug[4])), squash(drug[3])
        names = [n for n, _ in ingredients.get(code, [])]
        manufacturer = company.get(code, "")
        if not (brand and names and manufacturer):
            report["skipped_incomplete"] += 1
            continue
        if len(brand) > NAME_MAX:
            report["skipped_name_too_long"] += 1
            continue
        current = status.get(code, "")
        rows.append(
            {
                "brand_name": brand,
                "generic_name": join_generic(names),
                "manufacturer": title_words(manufacturer),
                "registration_number": din,
                "registration_status": STATUS.get(current, "unknown"),
                "composition": "; ".join(f"{n} {s}".strip() for n, s in ingredients[code]),
                "notes": f"Health Canada status: {current.title() or 'not stated'}.",
            }
        )
        report["rows"] += 1
    return Cleaned(rows, dict(report))
