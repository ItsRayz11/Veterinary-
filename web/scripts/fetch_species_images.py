"""Download one openly licensed photo per species from Wikipedia/Wikimedia Commons.

Run from `web/`:  python scripts/fetch_species_images.py

Each image is the lead picture of the species' Wikipedia article. It is kept only when its
Commons licence is open (CC0, public domain, CC BY, CC BY-SA); the credit its licence requires is
written to src/lib/image-credits.json and shown on the site. Nothing is stored for a species whose
image is not openly licensed, and the site falls back to an icon for it.
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "VetRefBot/1.0 (https://github.com/ItsRayz11/Veterinary-; image import)"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "species"
CREDITS = ROOT / "src" / "lib" / "image-credits.json"

# species slug -> Wikipedia article whose lead image shows that species or production class.
ARTICLES = {
    "cattle": "Cattle",
    "buffalo": "Water buffalo",
    "sheep": "Sheep",
    "goat": "Goat",
    "camel": "Camel",
    "horse": "Horse",
    "dog": "Dog",
    "cat": "Cat",
    "poultry": "Chicken",
    "broiler": "Broiler",
    "turkey": "Turkey (bird)",
    "rabbit": "Rabbit",
    "swine": "Pig",
}
OPEN = re.compile(r"^(cc0|public domain|pd\b|cc[ -]by(?:[ -]sa)?[ -][\d.]+)", re.I)


def api(params: dict) -> dict:
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def lead_file(article: str) -> str:
    data = api({"action": "query", "titles": article, "prop": "pageimages", "piprop": "name", "redirects": 1})
    for page in data["query"]["pages"].values():
        return page.get("pageimage", "")
    return ""


def file_info(name: str) -> dict | None:
    data = api(
        {
            "action": "query",
            "titles": f"File:{name}",
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": 800,
        }
    )
    for page in data["query"]["pages"].values():
        info = (page.get("imageinfo") or [None])[0]
        if not info:
            return None
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not OPEN.match(lic):
            print(f"  skipped (licence {lic!r})")
            return None
        artist = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", ""))).strip()
        return {
            "thumb": info.get("thumburl") or info["url"],
            "page": info.get("descriptionurl", ""),
            "credit": artist[:200] or "Wikimedia Commons contributors",
            "license": lic,
            "license_url": meta.get("LicenseUrl", {}).get("value", ""),
        }
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    credits = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else {}
    for slug, article in ARTICLES.items():
        print(slug, "<-", article)
        name = lead_file(article)
        info = file_info(name) if name else None
        if not info:
            continue
        dest = OUT / f"{slug}.jpg"
        req = urllib.request.Request(info["thumb"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
        credits.setdefault("species", {})[slug] = {
            "file": f"/species/{slug}.jpg",
            "source_article": article,
            "commons_file": name,
            "page": info["page"],
            "credit": info["credit"],
            "license": info["license"],
            "license_url": info["license_url"],
        }
        print(f"  ok {dest.stat().st_size // 1024} KB, {info['license']}")
    CREDITS.write_text(json.dumps(credits, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
