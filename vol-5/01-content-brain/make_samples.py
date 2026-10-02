"""Make the sample screenshots: text rendered into real PNGs, standard library only.

    python make_samples.py              # write sample-data/*.png (+ .txt sidecars)
    python make_samples.py --check      # also run tesseract and score each image

No PIL, no pip install. This builds the pixel grid by hand from a 5x7 bitmap
font, scales it up 8x so tesseract has something chunky to read, and writes a
valid PNG with zlib and struct: signature, IHDR, IDAT (filter byte 0 per
scanline), IEND.

Black text on white, uppercase only. All-caps bitmap glyphs are what tesseract
reads most reliably at this resolution, and a screenshot of a caption is a
plausible place for them.

Every PNG gets a matching .txt sidecar with the same text. That is not cheating:
it is the documented fallback path for machines without tesseract, and it means
the sample data still carries the project if OCR has a bad day.
"""

from __future__ import annotations

import argparse
import os
import struct
import subprocess
import zlib

SCALE = 8          # pixels per font pixel
CHAR_GAP = 1       # font pixels between glyphs
LINE_GAP = 4       # font pixels between baselines
MARGIN = 4         # font pixels of white around everything

# 5 wide, 7 tall. '#' is ink, '.' is paper.
FONT = {
    "A": "..#..|.#.#.|#...#|#####|#...#|#...#|#...#",
    "B": "####.|#...#|#...#|####.|#...#|#...#|####.",
    "C": ".###.|#...#|#....|#....|#....|#...#|.###.",
    "D": "####.|#...#|#...#|#...#|#...#|#...#|####.",
    "E": "#####|#....|#....|####.|#....|#....|#####",
    "F": "#####|#....|#....|####.|#....|#....|#....",
    "G": ".###.|#...#|#....|#.###|#...#|#...#|.###.",
    "H": "#...#|#...#|#...#|#####|#...#|#...#|#...#",
    "I": "#####|..#..|..#..|..#..|..#..|..#..|#####",
    "J": "..###|...#.|...#.|...#.|...#.|#..#.|.##..",
    "K": "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#",
    "L": "#....|#....|#....|#....|#....|#....|#####",
    "M": "#...#|##.##|#.#.#|#...#|#...#|#...#|#...#",
    "N": "#...#|##..#|##..#|#.#.#|#..##|#..##|#...#",
    "O": ".###.|#...#|#...#|#...#|#...#|#...#|.###.",
    "P": "####.|#...#|#...#|####.|#....|#....|#....",
    "Q": ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#",
    "R": "####.|#...#|#...#|####.|#.##.|#..##|#...#",
    "S": ".####|#....|#....|.###.|....#|....#|####.",
    "T": "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    "U": "#...#|#...#|#...#|#...#|#...#|#...#|.###.",
    "V": "#...#|#...#|#...#|#...#|.#.#.|.#.#.|..#..",
    "W": "#...#|#...#|#...#|#...#|#.#.#|#.#.#|.#.#.",
    "X": "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    "Y": "#...#|#...#|#...#|.#.#.|..#..|..#..|..#..",
    "Z": "#####|....#|...#.|..#..|.#...|#....|#####",
    "0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.",
    "1": "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
    "2": ".###.|#...#|....#|...#.|..#..|.#...|#####",
    "3": "#####|...#.|..#..|...#.|....#|#...#|.###.",
    "4": "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.",
    "5": "#####|#....|####.|....#|....#|#...#|.###.",
    "6": "..##.|.#...|#....|####.|#...#|#...#|.###.",
    "7": "#####|....#|...#.|..#..|.#...|.#...|.#...",
    "8": ".###.|#...#|#...#|.###.|#...#|#...#|.###.",
    "9": ".###.|#...#|#...#|.####|....#|...#.|.##..",
    " ": ".....|.....|.....|.....|.....|.....|.....",
    "?": ".###.|#...#|....#|...#.|..#..|.....|..#..",
    "!": "..#..|..#..|..#..|..#..|..#..|.....|..#..",
    ".": ".....|.....|.....|.....|.....|.##..|.##..",
    ",": ".....|.....|.....|.....|.##..|.##..|.#...",
    "'": "..#..|..#..|.....|.....|.....|.....|.....",
    ":": ".....|.##..|.##..|.....|.##..|.##..|.....",
    "-": ".....|.....|.....|#####|.....|.....|.....",
    "/": "....#|...#.|...#.|..#..|.#...|.#...|#....",
    "$": "..#..|.####|#.#..|.###.|..#.#|####.|..#..",
    "(": "...#.|..#..|.#...|.#...|.#...|..#..|...#.",
    ")": ".#...|..#..|...#.|...#.|...#.|..#..|.#...",
    "@": ".###.|#...#|#.###|#.#.#|#.###|#....|.###.",
    "#": ".#.#.|.#.#.|#####|.#.#.|#####|.#.#.|.#.#.",
}

GLYPH_W, GLYPH_H = 5, 7


def glyph(ch: str) -> list[str]:
    return FONT.get(ch.upper(), FONT["?"]).split("|")


def render_grid(lines: list[str]) -> list[bytearray]:
    """Return a grid of font pixels (1 = ink) for the given text lines."""
    widest = max(len(line) for line in lines)
    w = MARGIN * 2 + widest * (GLYPH_W + CHAR_GAP) - CHAR_GAP
    h = MARGIN * 2 + len(lines) * (GLYPH_H + LINE_GAP) - LINE_GAP
    grid = [bytearray(w) for _ in range(h)]
    for row, line in enumerate(lines):
        top = MARGIN + row * (GLYPH_H + LINE_GAP)
        for col, ch in enumerate(line):
            left = MARGIN + col * (GLYPH_W + CHAR_GAP)
            for y, bits in enumerate(glyph(ch)):
                for x, bit in enumerate(bits):
                    if bit == "#":
                        grid[top + y][left + x] = 1
    return grid


def png_bytes(grid: list[bytearray], scale: int = SCALE) -> bytes:
    """Encode a font-pixel grid as an 8-bit greyscale PNG, scaled up."""
    w, h = len(grid[0]) * scale, len(grid) * scale
    raw = bytearray()
    for row in grid:
        scanline = bytes(0 if bit else 255 for bit in row for _ in range(scale))
        for _ in range(scale):
            raw.append(0)          # filter type 0: no filtering
            raw += scanline

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)   # 8-bit, greyscale
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


# The sample inbox. Each entry is a filename stem plus the lines to render.
# Written uppercase because that is what the bitmap font has, and what OCR
# reads best here. The sidecar .txt holds the identical text.
SHOTS = {
    "screenshot-budget-hook": [
        "SAVED POST",
        "THE BEST BUDGETING VIDEO",
        "HOOK I HAVE SEEN: SHOW",
        "THE EMPTY ENVELOPE FIRST,",
        "THEN FILL IT ON CAMERA.",
    ],
    "screenshot-spreadsheet-dm": [
        "DM FROM MARA",
        "HEY, CAN YOU SEND THE",
        "BUDGET SPREADSHEET",
        "TEMPLATE YOU USED IN THE",
        "MONEY VIDEO? THOUGHTS ON",
        "A FREE TIER VERSION?",
    ],
    "screenshot-ocr-receipts": [
        "SAVED POST",
        "SOMEONE BUILT A RECEIPT",
        "SCANNER WITH TESSERACT",
        "OCR IN EIGHTY LINES",
        "OF PYTHON, NO KEY NEEDED.",
    ],
    "screenshot-plant-light": [
        "NOTE TO SELF",
        "THE MONSTERA BY THE",
        "NORTH WINDOW IS LEANING.",
        "MOVE IT AND FILM THE",
        "LIGHT TEST FOR THE PLANT",
        "SERIES.",
    ],
    "screenshot-random-poster": [
        "FLYER",
        "OPEN MIC NIGHT",
        "THURSDAY EVENING",
        "BRING A FRIEND",
    ],
}


def write_samples(out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for stem, lines in SHOTS.items():
        png_path = os.path.join(out_dir, stem + ".png")
        txt_path = os.path.join(out_dir, stem + ".txt")
        with open(png_path, "wb") as f:
            f.write(png_bytes(render_grid(lines)))
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        written.append(png_path)
    return written


def check(png_path: str, expected: list[str]) -> None:
    """Run tesseract on one PNG and report word recall against the source text."""
    try:
        out = subprocess.run(
            ["tesseract", png_path, "stdout", "--psm", "6"],
            capture_output=True, text=True, errors="replace", check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"{os.path.basename(png_path)}: tesseract unavailable ({e})")
        return
    got = {w.strip(".,:?!'()").upper() for w in out.split()}
    want = [w.strip(".,:?!'()").upper() for w in " ".join(expected).split()]
    hits = sum(1 for w in want if w in got)
    print(f"{os.path.basename(png_path)}: {hits}/{len(want)} words read back "
          f"({hits / len(want):.0%})")
    missed = [w for w in want if w not in got]
    if missed:
        print(f"    missed: {' '.join(missed)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sample-data")
    ap.add_argument("--check", action="store_true", help="run tesseract on each PNG")
    args = ap.parse_args()

    paths = write_samples(args.out)
    print(f"Wrote {len(paths)} PNGs and {len(paths)} .txt sidecars to {args.out}/")
    if args.check:
        for stem, lines in SHOTS.items():
            check(os.path.join(args.out, stem + ".png"), lines)


if __name__ == "__main__":
    main()
