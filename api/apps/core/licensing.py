"""Licence recognition shared by importers and the image pipeline.

Open licences only. Anything else (non-free logo, fair use, unknown) is treated as not
redistributable. Deterministic string rules, no network, no AI.
"""

import re

_OPEN_LICENSE = re.compile(r"^(cc0|public domain|pd\b|cc[ -]by(?:[ -]sa)?[ -][\d.]+)", re.I)
# Licences that legally require the credit (and ideally a link back) to travel with the file.
_ATTRIBUTION = re.compile(r"^cc[ -]by", re.I)


def is_open_license(short_name: str) -> bool:
    return bool(_OPEN_LICENSE.match((short_name or "").strip()))


def requires_attribution(short_name: str) -> bool:
    return bool(_ATTRIBUTION.match((short_name or "").strip()))
