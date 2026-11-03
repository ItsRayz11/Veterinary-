"""Import veterinary schools from Wikipedia categories and Wikidata.

Why these sources: both are openly licensed (Wikipedia text CC BY-SA, Wikidata CC0), have a public
API and are attributable per record. Nothing here is treated as verified: every created row is
`imported_unverified` and shows as such until an editor reviews it. Images are kept only when the
Commons file carries an open licence, together with the credit that licence requires.

All network access goes through the injectable `fetch` so the parsing and filtering rules can be
tested offline.
"""

import json
import re
import urllib.parse
import urllib.request
from collections.abc import Callable

from apps.core.reference_data import UNIVERSITY_SOURCES

USER_AGENT = "VetRefBot/1.0 (https://github.com/ItsRayz11/Veterinary-; data import)"
WIKIPEDIA = "en.wikipedia.org"
WIKIDATA = "www.wikidata.org"

# Pages that sit in the categories but are not schools.
_NOT_A_SCHOOL = re.compile(r"^(list of|category:)|admission test|training institute", re.I)
_RELEVANT = re.compile(r"veterinar|animal science", re.I)
_INSTITUTION = re.compile(r"college|school|faculty|universit|institute|cent(?:er|re)", re.I)
_NOT_AN_INSTITUTION = re.compile(
    r"association|council|board|society|surgeons|veterinarians|application service", re.I
)
# Open licences only. Anything else (non-free logo, fair use, unknown) means no image.
_OPEN_LICENSE = re.compile(r"^(cc0|public domain|pd\b|cc[ -]by(?:[ -]sa)?[ -][\d.]+)", re.I)
_TAGS = re.compile(r"<[^>]+>")

Fetch = Callable[[str, dict], dict]


def api_fetch(host: str, params: dict) -> dict:
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https hosts
        return json.load(resp)


def is_school_title(title: str) -> bool:
    return not _NOT_A_SCHOOL.search(title)


def is_relevant(title: str, extract: str) -> bool:
    """A veterinary teaching institution: the name or the first sentence says so, and the page is
    about an institution rather than a body such as an association or a council."""
    first = re.split(r"(?<=[.!?])\s", extract.strip(), maxsplit=1)[0]
    if _NOT_AN_INSTITUTION.search(title) or not _INSTITUTION.search(title):
        return False
    return bool(_RELEVANT.search(f"{title} {first}"))


def clean_name(title: str) -> str:
    """The page title is the name; parentheses (a campus, say) are informative, so they stay."""
    return title.strip()[:200]


def is_open_license(short_name: str) -> bool:
    return bool(_OPEN_LICENSE.match(short_name.strip()))


def strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", _TAGS.sub("", value)).strip()


def category_titles(fetch: Fetch, categories: list[str]) -> list[str]:
    titles: list[str] = []
    for cat in categories:
        data = fetch(
            WIKIPEDIA,
            {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmlimit": 200},
        )
        titles += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
    return [t for t in dict.fromkeys(titles) if is_school_title(t)]


def list_page_titles(fetch: Fetch, pages: list[str]) -> list[str]:
    titles: list[str] = []
    for page in pages:
        data = fetch(
            WIKIPEDIA,
            {"action": "parse", "page": page, "prop": "links", "redirects": 1},
        )
        titles += [
            link["*"]
            for link in data.get("parse", {}).get("links", [])
            if link.get("ns") == 0 and "exists" in link
        ]
    return [t for t in dict.fromkeys(titles) if is_school_title(t)]


def page_info(fetch: Fetch, titles: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 20):
        data = fetch(
            WIKIPEDIA,
            {
                "action": "query",
                "titles": "|".join(titles[i : i + 20]),
                "prop": "extracts|pageprops|pageimages|info",
                "exintro": 1,
                "explaintext": 1,
                "exsentences": 3,
                "exlimit": "max",
                "ppprop": "wikibase_item",
                "piprop": "name",
                "inprop": "url",
                "redirects": 1,
            },
        )
        query = data.get("query", {})
        # Titles the caller asked for that resolve to each page (normalisation, then redirects).
        asked: dict[str, set[str]] = {}
        step1 = {n["to"]: n["from"] for n in query.get("normalized", [])}
        for r in query.get("redirects", []):
            asked.setdefault(r["to"], set()).add(step1.get(r["from"], r["from"]))
        for page in query.get("pages", {}).values():
            if "missing" in page:
                continue
            out[page["title"]] = {
                "requested": asked.get(page["title"], set())
                | {step1.get(page["title"], page["title"])},
                "extract": (page.get("extract") or "").strip(),
                "qid": page.get("pageprops", {}).get("wikibase_item", ""),
                "image_file": page.get("pageimage", ""),
                "url": page.get("fullurl", ""),
            }
    return out


def _claim_values(entity: dict, prop: str) -> list:
    out = []
    for claim in entity.get("claims", {}).get(prop, []):
        snak = claim.get("mainsnak", {})
        if snak.get("datavalue"):
            out.append(snak["datavalue"]["value"])
    return out


def wikidata_facts(fetch: Fetch, qids: list[str]) -> dict[str, dict]:
    """Official website, coordinates, founding year, city and logo file for each item."""
    facts: dict[str, dict] = {}
    city_ids: set[str] = set()
    for i in range(0, len(qids), 50):
        data = fetch(
            WIKIDATA,
            {"action": "wbgetentities", "ids": "|".join(qids[i : i + 50]), "props": "claims"},
        )
        for qid, ent in data.get("entities", {}).items():
            sites = _claim_values(ent, "P856")
            coords = _claim_values(ent, "P625")
            inception = _claim_values(ent, "P571")
            places = [v["id"] for v in _claim_values(ent, "P131") if isinstance(v, dict)]
            countries = [v["id"] for v in _claim_values(ent, "P17") if isinstance(v, dict)]
            logos = _claim_values(ent, "P154")
            year = None
            if inception and isinstance(inception[0], dict):
                m = re.match(r"^\+?(\d{4})", inception[0].get("time", ""))
                year = int(m.group(1)) if m else None
            facts[qid] = {
                "website": sites[0] if sites and isinstance(sites[0], str) else "",
                "lat": coords[0].get("latitude") if coords else None,
                "lon": coords[0].get("longitude") if coords else None,
                "year": year,
                "place_id": places[0] if places else "",
                "country_ids": countries,
                "logo_file": logos[0] if logos and isinstance(logos[0], str) else "",
            }
            city_ids.update(p for p in places[:1])
    labels = _labels(fetch, sorted(city_ids))
    for f in facts.values():
        f["city"] = labels.get(f.pop("place_id"), "")
    return facts


def _labels(fetch: Fetch, ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(ids), 50):
        data = fetch(
            WIKIDATA,
            {
                "action": "wbgetentities",
                "ids": "|".join(ids[i : i + 50]),
                "props": "labels",
                "languages": "en",
            },
        )
        for qid, ent in data.get("entities", {}).items():
            out[qid] = ent.get("labels", {}).get("en", {}).get("value", "")
    return out


def open_image(fetch: Fetch, filename: str) -> dict | None:
    """Thumbnail URL and credit for a file, only when its licence is open. Else None."""
    if not filename:
        return None
    title = filename if filename.startswith("File:") else f"File:{filename}"
    data = fetch(
        WIKIPEDIA,
        {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": 640,
        },
    )
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [None])[0]
        if not info:
            continue
        meta = info.get("extmetadata", {})
        license_name = meta.get("LicenseShortName", {}).get("value", "")
        if not is_open_license(license_name):
            return None
        artist = strip_html(meta.get("Artist", {}).get("value", ""))
        return {
            "url": (info.get("thumburl") or info.get("url", "")).split("?")[0],
            "page_url": info.get("descriptionurl", ""),
            "credit": artist[:300] or "Wikimedia Commons contributors",
            "license": license_name[:80],
            "license_url": meta.get("LicenseUrl", {}).get("value", "")[:300],
        }
    return None


def collect(fetch: Fetch, iso2: str) -> list[dict]:
    """Everything the importer would store for one country, as plain dicts."""
    titles = category_titles(fetch, UNIVERSITY_SOURCES[iso2]["categories"])
    # Links on a list page are only candidates; their Wikidata country must match (checked below).
    from_list = [
        t
        for t in list_page_titles(fetch, UNIVERSITY_SOURCES[iso2].get("list_pages", []))
        if t not in titles
    ]
    titles += from_list
    category_set = set(titles) - set(from_list)
    pages = page_info(fetch, titles)
    kept = {t: p for t, p in pages.items() if is_relevant(t, p["extract"])}
    facts = wikidata_facts(fetch, sorted({p["qid"] for p in kept.values() if p["qid"]}))
    rows = []
    for title, p in kept.items():
        f = facts.get(p["qid"], {})
        if not (p["requested"] & category_set) and UNIVERSITY_SOURCES[iso2][
            "wikidata"
        ] not in f.get("country_ids", []):
            continue
        # Prefer the official logo; fall back to the article's lead image.
        image = open_image(fetch, f.get("logo_file", "")) or open_image(fetch, p["image_file"])
        rows.append(
            {
                "name": clean_name(title),
                "summary": p["extract"],
                "source_url": p["url"],
                "wikidata_id": p["qid"],
                "website": f.get("website", ""),
                "city": f.get("city", ""),
                "founded_year": f.get("year"),
                "latitude": round(f["lat"], 6) if f.get("lat") is not None else None,
                "longitude": round(f["lon"], 6) if f.get("lon") is not None else None,
                "image": image,
            }
        )
    return rows
