"""US DailyMed animal drug labels (FDA Center for Veterinary Medicine, published by the US NLM).

Source: https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?doctype=<code>, then each
label's SPL XML. Only the two animal document types are read (50576-8 prescription, 50577-6 OTC).

Only listing facts are taken: product name, active ingredients, strength text, dosage form,
labeller and marketing category/application number. Label text (indications, dosing, species,
withdrawal times, warnings) is never read, because it is clinical content for the US market and
would need clinical review. Every row is US-specific by construction (the importer's country).
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

from defusedxml import ElementTree

from apps.automation import safe_http

from .common import NAME_MAX, Cleaned, join_generic, squash, title_words

API = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
DOCTYPES = ("50577-6", "50576-8")  # OTC animal, prescription animal
PAGE_SIZE = 100
MAX_LABELS = 6000
BUDGET_SECONDS = 3000
NS = {"h": "urn:hl7-org:v3"}
APPROVED = re.compile(r"^(CONDITIONAL )?(NADA|ANADA)\b|^BLA\b", re.I)


def _get(url: str) -> bytes:
    deadline = time.monotonic() + 60
    status, body, _final, _headers = safe_http.fetch_full(
        url, max_bytes=5_000_000, timeout=30, deadline=deadline
    )
    if status != 200:
        raise ValueError(f"HTTP {status} for {url}")
    return body


def parse_label(xml: bytes) -> list[dict]:
    """Rows (one per product in the label) from one SPL document; [] for unusable labels."""
    root = ElementTree.fromstring(xml)
    doc = root.find("h:code", NS)
    if doc is None or doc.get("code") not in DOCTYPES:
        return []
    sid = root.find("h:setId", NS)
    set_id = sid.get("root", "") if sid is not None else ""
    org = root.find("h:author//h:representedOrganization/h:name", NS)
    labeller = squash(org.text or "") if org is not None else ""
    rows = []
    for product in root.iterfind(".//h:manufacturedProduct/h:manufacturedProduct", NS):
        name_el = product.find("h:name", NS)
        brand = squash("".join(name_el.itertext())) if name_el is not None else ""
        actives, strengths = [], []
        for ing in product.iterfind("h:ingredient", NS):
            if ing.get("classCode") not in ("ACTIB", "ACTIM", "ACTIR"):
                continue
            sub = ing.find("h:ingredientSubstance/h:name", NS)
            if sub is None or not (sub.text or "").strip():
                continue
            actives.append(title_words(squash(sub.text)))
            num = ing.find("h:quantity/h:numerator", NS)
            den = ing.find("h:quantity/h:denominator", NS)
            if num is not None and num.get("value"):
                text = f"{num.get('value')} {num.get('unit', '')}".strip()
                if den is not None and den.get("value"):
                    text += f" per {den.get('value')} {den.get('unit', '')}".rstrip()
                strengths.append(f"{actives[-1]} {text}")
        form = product.find("h:formCode", NS)
        category = number = ""
        for approval in product.iterfind(".//h:approval", NS):
            code = approval.find("h:code", NS)
            if code is not None:
                category = squash(code.get("displayName", ""))
                ident = approval.find("h:id", NS)
                number = squash(ident.get("extension", "")) if ident is not None else ""
                break
        if not (brand and actives and labeller):
            continue
        rows.append(
            {
                "set_id": set_id,
                "brand_name": title_words(brand) if brand.isupper() else brand,
                "generic_name": join_generic(actives),
                "manufacturer": title_words(labeller) if labeller.isupper() else labeller,
                "category": category,
                "number": number,
                "composition": "; ".join(strengths),
                "form": form.get("displayName", "") if form is not None else "",
            }
        )
    return rows


def _to_import_row(raw: dict, seen: set[str]) -> dict | None:
    if len(raw["brand_name"]) > NAME_MAX:
        return None
    number = raw["number"]
    if not number or number in seen:
        number = f"DailyMed {raw['set_id']}"
    if number in seen:
        return None
    seen.add(number)
    approved = bool(APPROVED.match(raw["category"]))
    notes = (
        f"US FDA marketing category: {raw['category'] or 'not stated'}"
        f"{f' {raw["number"]}' if raw['number'] else ''}. "
        "United States labelling; says nothing about availability or approval in other countries."
    )
    return {
        "brand_name": raw["brand_name"],
        "generic_name": raw["generic_name"],
        "manufacturer": raw["manufacturer"],
        "registration_number": number,
        "registration_status": "registered" if approved else "unknown",
        "composition": raw["composition"],
        "notes": notes + (f" Dosage form: {raw['form'].title()}." if raw["form"] else ""),
    }


def _listing(doctype: str, first_page: bytes | None) -> list[str]:
    ids: list[str] = []
    page = 1
    while True:
        url = f"{API}/spls.json?pagesize={PAGE_SIZE}&doctype={doctype}&page={page}"
        data = json.loads(first_page if (first_page and page == 1) else _get(url))
        ids += [d["setid"] for d in data.get("data", []) if d.get("setid")]
        meta = data.get("metadata", {})
        if page >= int(meta.get("total_pages", 1)) or len(ids) >= MAX_LABELS:
            return ids[:MAX_LABELS]
        page += 1


def clean_listing(body: bytes) -> Cleaned:
    """`body` is the first listing page of the OTC document type (the source's data URL)."""
    started = time.monotonic()
    first = json.loads(body)
    first_doctype = re.search(
        r"doctype=([0-9-]+)", first.get("metadata", {}).get("current_url", "")
    )
    ids: list[str] = []
    for doctype in DOCTYPES:
        use_body = body if first_doctype and first_doctype.group(1) == doctype else None
        ids += _listing(doctype, use_body)
    ids = list(dict.fromkeys(ids))[:MAX_LABELS]
    report = {"labels_listed": len(ids), "labels_read": 0, "skipped_unreadable": 0}

    def read(set_id):
        if time.monotonic() - started > BUDGET_SECONDS:
            return None
        try:
            return parse_label(_get(f"{API}/spls/{set_id}.xml"))
        except Exception:  # noqa: BLE001 - one broken label must not stop the run
            return None

    rows, seen = [], set()
    with ThreadPoolExecutor(max_workers=6) as pool:
        for parsed in pool.map(read, ids):
            if parsed is None:
                report["skipped_unreadable"] += 1
                continue
            report["labels_read"] += 1
            for raw in parsed:
                row = _to_import_row(raw, seen)
                if row:
                    rows.append(row)
    report["rows"] = len(rows)
    report["entries"] = len(ids)
    report["skipped_incomplete"] = report["skipped_unreadable"]
    return Cleaned(rows, report)
