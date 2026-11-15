"""Known publishers whose identity we can verify from a URL alone.

A provider says: URLs on these hosts belong to this publisher, and its content is offered under
this licence. This is how a raw URL is resolved to a *provider identity* rather than trusted
as-is. Anything not listed here stays unverified until a person or a registered DataSource vouches
for it. Licence strings are the publishers' own published terms, not assertions of ours.
"""

from dataclasses import dataclass

from apps.core.licensing import is_open_license

from .urlutil import host_of


@dataclass(frozen=True)
class Provider:
    slug: str
    name: str
    publisher: str
    host_suffixes: tuple[str, ...]
    license_note: str
    license_url: str
    source_type: str = "other"

    @property
    def open_license(self) -> bool:
        return is_open_license(self.license_note)


PROVIDERS = (
    Provider(
        "wikipedia",
        "Wikipedia",
        "Wikimedia Foundation",
        ("wikipedia.org",),
        "CC BY-SA 4.0 (Wikipedia)",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    Provider(
        "wikidata",
        "Wikidata",
        "Wikimedia Foundation",
        ("wikidata.org",),
        "CC0 1.0 (Wikidata)",
        "https://creativecommons.org/publicdomain/zero/1.0/",
    ),
    Provider(
        "wikimedia-commons",
        "Wikimedia Commons",
        "Wikimedia Foundation",
        ("commons.wikimedia.org", "upload.wikimedia.org"),
        "Per-file open licence (see file page)",
        "https://commons.wikimedia.org/wiki/Commons:Licensing",
    ),
)


def provider_for_url(url: str) -> Provider | None:
    host = host_of(url)
    for p in PROVIDERS:
        if any(host == s or host.endswith("." + s) for s in p.host_suffixes):
            return p
    return None


def provider_by_slug(slug: str) -> Provider | None:
    return next((p for p in PROVIDERS if p.slug == slug), None)
