"""Upload scanning for 3D models.

Three layers, all recorded on the catalog row:

1. Built-in deep GLB inspection (always on, no external service): the container must be a
   well-formed glTF 2.0 binary; the JSON must parse; no external or script-bearing URIs; only
   allow-listed extensions; sane counts. This blocks the practical ways a model file can carry
   active content or pull remote resources.
2. ClamAV (optional): set CLAMD_HOST (and CLAMD_PORT, default 3310) to a clamd daemon and the file
   is streamed to it with INSTREAM.
3. VirusTotal hash lookup (optional): set VIRUSTOTAL_API_KEY and the SHA-256 is looked up (the file
   itself is never uploaded). An unknown hash is not treated as a verdict.

Nothing here can prove a file is safe. A model becomes eligible for approval only when every
configured layer returned clean; moderators still review it visually.
"""

import hashlib
import json
import os
import socket
import struct
import urllib.error
import urllib.request

CLEAN, SUSPICIOUS, INFECTED, ERROR = "clean", "suspicious", "infected", "error"

# Extensions the web viewer can render without fetching a remote decoder (CSP forbids remote
# origins). Compressed-mesh extensions need a decoder from a CDN, so they are rejected.
ALLOWED_EXTENSIONS = {
    "KHR_materials_unlit", "KHR_materials_emissive_strength", "KHR_materials_clearcoat",
    "KHR_materials_ior", "KHR_materials_specular", "KHR_materials_transmission",
    "KHR_materials_volume", "KHR_materials_sheen", "KHR_materials_variants",
    "KHR_texture_transform", "KHR_mesh_quantization", "KHR_lights_punctual",
}  # fmt: skip
MAX_COUNT = 20_000  # nodes/meshes/materials/accessors etc. each


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _uri_problem(uri: str) -> str | None:
    u = uri.strip().lower()
    if u.startswith("data:"):
        head = u.split(",", 1)[0]
        if not (head.startswith("data:image/") or head.startswith("data:application/octet-stream")):
            return "embedded data of an unexpected type"
        if "script" in head or "html" in head or "svg" in head:
            return "embedded script-capable data"
        return None
    return "references an external file or URL"


def inspect_glb(data: bytes) -> tuple[str, str]:
    """Built-in layer. Returns (status, detail)."""
    try:
        chunk_len = struct.unpack_from("<I", data, 12)[0]
        doc = json.loads(data[20 : 20 + chunk_len].decode("utf-8").rstrip("\x00 "))
    except (struct.error, UnicodeDecodeError, ValueError):
        return SUSPICIOUS, "The glTF JSON chunk could not be parsed."
    if not isinstance(doc, dict):
        return SUSPICIOUS, "The glTF JSON is not an object."
    required = set(doc.get("extensionsRequired") or [])
    used = set(doc.get("extensionsUsed") or [])
    bad_ext = (required | used) - ALLOWED_EXTENSIONS
    if bad_ext:
        return (
            SUSPICIOUS,
            f"Unsupported or compressed-mesh extension(s): {', '.join(sorted(bad_ext))[:120]}",
        )
    for key in ("buffers", "images"):
        for item in doc.get(key) or []:
            uri = item.get("uri") if isinstance(item, dict) else None
            if uri:
                problem = _uri_problem(str(uri))
                if problem:
                    return SUSPICIOUS, f"A {key[:-1]} {problem}."
    for key in ("nodes", "meshes", "materials", "accessors", "textures", "images", "buffers"):
        v = doc.get(key) or []
        if isinstance(v, list) and len(v) > MAX_COUNT:
            return SUSPICIOUS, f"Unusually many {key} ({len(v)})."
    if b"<script" in data.lower() or b"javascript:" in data.lower():
        return SUSPICIOUS, "Contains script markers."
    return CLEAN, "Structure and references look normal."


def clamav(data: bytes) -> tuple[str, str] | None:
    host = os.environ.get("CLAMD_HOST")
    if not host:
        return None
    try:
        with socket.create_connection((host, int(os.environ.get("CLAMD_PORT", "3310"))), 5) as s:
            s.settimeout(30)
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 65536):
                part = data[i : i + 65536]
                s.sendall(struct.pack("!I", len(part)) + part)
            s.sendall(struct.pack("!I", 0))
            reply = s.recv(4096).decode("utf-8", "replace").strip("\0\n ")
    except (OSError, ValueError) as exc:
        return ERROR, f"ClamAV unreachable ({type(exc).__name__})."
    if reply.endswith("OK"):
        return CLEAN, "ClamAV: no threat found."
    if "FOUND" in reply:
        return INFECTED, f"ClamAV: {reply.split(':', 1)[-1].strip()[:100]}"
    return ERROR, "ClamAV returned an unexpected reply."


def virustotal(digest: str) -> tuple[str, str] | None:
    key = os.environ.get("VIRUSTOTAL_API_KEY")
    if not key:
        return None
    req = urllib.request.Request(  # noqa: S310 - fixed https host
        f"https://www.virustotal.com/api/v3/files/{digest}", headers={"x-apikey": key}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            stats = json.loads(resp.read(500_000))["data"]["attributes"]["last_analysis_stats"]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return CLEAN, "VirusTotal: hash not known (no verdict, not a clearance)."
        return ERROR, f"VirusTotal returned HTTP {exc.code}."
    except (OSError, ValueError, KeyError):
        return ERROR, "VirusTotal lookup failed."
    if stats.get("malicious", 0) > 0:
        return INFECTED, f"VirusTotal: {stats['malicious']} engine(s) flag this file."
    if stats.get("suspicious", 0) > 0:
        return SUSPICIOUS, f"VirusTotal: {stats['suspicious']} engine(s) call it suspicious."
    return CLEAN, "VirusTotal: no engine flags this file."


def scan(data: bytes) -> tuple[str, str, str]:
    """Run every configured layer. Returns (status, detail, sha256); worst result wins."""
    digest = sha256(data)
    order = {CLEAN: 0, ERROR: 1, SUSPICIOUS: 2, INFECTED: 3}
    results = [inspect_glb(data), clamav(data), virustotal(digest)]
    results = [r for r in results if r]
    worst = max(results, key=lambda r: order[r[0]])
    detail = " ".join(r[1] for r in results)[:290]
    return worst[0], detail, digest
