"""Write the sample PNGs in sample-data/, using only the standard library.

    python make_samples.py

There is no PIL here on purpose. A PNG is a signature, an IHDR chunk, zlib
compressed scanlines each prefixed with a filter byte, and an IEND chunk. That
is the whole format for our case, and it is about 30 lines.

The images stand in for a real photo so you can exercise the --ai vision path.
Each one gets a .txt sidecar naming its foods, which is what the default
no-key path reads.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent / "sample-data"

# A 3x5 bitmap font, five rows per glyph, scaled up when drawn.
GLYPHS = {
    "A": ("###", "# #", "###", "# #", "# #"),
    "B": ("## ", "# #", "## ", "# #", "## "),
    "C": ("###", "#  ", "#  ", "#  ", "###"),
    "D": ("## ", "# #", "# #", "# #", "## "),
    "E": ("###", "#  ", "###", "#  ", "###"),
    "F": ("###", "#  ", "###", "#  ", "#  "),
    "G": ("###", "#  ", "# #", "# #", "###"),
    "H": ("# #", "# #", "###", "# #", "# #"),
    "I": ("###", " # ", " # ", " # ", "###"),
    "J": ("###", "  #", "  #", "# #", "###"),
    "K": ("# #", "# #", "## ", "# #", "# #"),
    "L": ("#  ", "#  ", "#  ", "#  ", "###"),
    "M": ("# #", "###", "###", "# #", "# #"),
    "N": ("## ", "# #", "# #", "# #", "# #"),
    "O": ("###", "# #", "# #", "# #", "###"),
    "P": ("###", "# #", "###", "#  ", "#  "),
    "Q": ("###", "# #", "###", "  #", "  #"),
    "R": ("###", "# #", "## ", "# #", "# #"),
    "S": ("###", "#  ", "###", "  #", "###"),
    "T": ("###", " # ", " # ", " # ", " # "),
    "U": ("# #", "# #", "# #", "# #", "###"),
    "V": ("# #", "# #", "# #", "# #", " # "),
    "W": ("# #", "# #", "###", "###", "# #"),
    "X": ("# #", "# #", " # ", "# #", "# #"),
    "Y": ("# #", "# #", " # ", " # ", " # "),
    "Z": ("###", "  #", " # ", "#  ", "###"),
    "0": ("###", "# #", "# #", "# #", "###"),
    "1": (" # ", "## ", " # ", " # ", "###"),
    "2": ("###", "  #", "###", "#  ", "###"),
    "3": ("###", "  #", "###", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"),
    "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"),
    "7": ("###", "  #", "  #", " # ", " # "),
    "8": ("###", "# #", "###", "# #", "###"),
    "9": ("###", "# #", "###", "  #", "###"),
    " ": ("   ", "   ", "   ", "   ", "   "),
    "-": ("   ", "   ", "###", "   ", "   "),
    ".": ("   ", "   ", "   ", "   ", " # "),
    ",": ("   ", "   ", "   ", " # ", "#  "),
    "&": ("## ", "## ", "###", "# #", "###"),
}
GLYPH_W, GLYPH_H = 3, 5


def blank(width: int, height: int, color: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    return [[color for _ in range(width)] for _ in range(height)]


def fill(canvas, x: int, y: int, w: int, h: int, color) -> None:
    for row in range(y, min(y + h, len(canvas))):
        for col in range(x, min(x + w, len(canvas[0]))):
            if row >= 0 and col >= 0:
                canvas[row][col] = color


def text(canvas, x: int, y: int, label: str, color, scale: int = 3) -> None:
    for n, char in enumerate(label.upper()):
        bits = GLYPHS.get(char, GLYPHS[" "])
        for row in range(GLYPH_H):
            for col in range(GLYPH_W):
                if bits[row][col] == "#":
                    px = x + n * (GLYPH_W + 1) * scale + col * scale
                    fill(canvas, px, y + row * scale, scale, scale, color)


def chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def write_png(path: Path, canvas) -> None:
    height, width = len(canvas), len(canvas[0])
    raw = bytearray()
    for row in canvas:
        raw.append(0)  # filter type 0, none, one byte per scanline
        for r, g, b in row:
            raw += bytes((r, g, b))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, truecolor RGB
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def plate(title: str, blocks: list[tuple[str, tuple[int, int, int]]]) -> list:
    """A labelled colour block per food, laid out as a 2x2 plate."""
    width, height = 640, 480
    canvas = blank(width, height, (244, 241, 234))
    text(canvas, 24, 24, title, (40, 44, 54), scale=4)
    for n, (label, color) in enumerate(blocks):
        x = 40 + (n % 2) * 290
        y = 90 + (n // 2) * 185
        fill(canvas, x, y, 260, 155, color)
        text(canvas, x + 14, y + 124, label, (255, 255, 255), scale=3)
    return canvas


SAMPLES = [
    {
        "file": "plate-lentils-tea.png",
        "title": "Plate 1",
        "foods": "lentils, spinach, brown rice, black tea",
        "blocks": [
            ("LENTILS", (150, 92, 62)),
            ("SPINACH", (58, 94, 54)),
            ("BROWN RICE", (176, 150, 112)),
            ("BLACK TEA", (84, 54, 40)),
        ],
    },
    {
        "file": "plate-chicken-pepper.png",
        "title": "Plate 2",
        "foods": "chicken breast, bell pepper, white rice, broccoli",
        "blocks": [
            ("CHICKEN", (206, 172, 124)),
            ("BELL PEPPER", (190, 54, 48)),
            ("WHITE RICE", (232, 228, 214)),
            ("BROCCOLI", (74, 118, 62)),
        ],
    },
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        png = OUT / sample["file"]
        write_png(png, plate(sample["title"], sample["blocks"]))
        png.with_suffix(".txt").write_text(sample["foods"] + "\n", encoding="utf-8")
        print(f"wrote {png.name} and {png.with_suffix('.txt').name}")


if __name__ == "__main__":
    main()
