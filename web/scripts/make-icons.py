"""Generates the PWA icons (teal rounded square with a white cross) using only the stdlib.

Run: python web/scripts/make-icons.py   (writes web/public/icons/*.png)
"""

import struct
import zlib
from pathlib import Path

TEAL = (11, 110, 110)
WHITE = (255, 255, 255)
OUT = Path(__file__).resolve().parent.parent / "public" / "icons"


def png(size: int, pixel) -> bytes:
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            rows.extend(pixel(x, y))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def icon(size: int, maskable: bool):
    radius = 0 if maskable else size * 0.22  # maskable icons are cropped by the OS
    arm = size * (0.09 if maskable else 0.10)  # half thickness of the cross bars
    reach = size * (0.22 if maskable else 0.28)  # keeps the mark inside the safe zone
    c = size / 2

    def inside_round(x, y):
        if radius == 0:
            return True
        dx = max(radius - x, x - (size - 1 - radius), 0)
        dy = max(radius - y, y - (size - 1 - radius), 0)
        return dx * dx + dy * dy <= radius * radius

    def pixel(x, y):
        if not inside_round(x, y):
            return (255, 255, 255)
        horizontal = abs(y - c) <= arm and abs(x - c) <= reach
        vertical = abs(x - c) <= arm and abs(y - c) <= reach
        return WHITE if horizontal or vertical else TEAL

    return png(size, pixel)


OUT.mkdir(parents=True, exist_ok=True)
for name, size, maskable in (
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, True),
):
    (OUT / name).write_bytes(icon(size, maskable))
    print("wrote", name)
