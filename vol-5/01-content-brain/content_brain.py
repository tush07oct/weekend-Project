"""Content Brain, shared guts: read an inbox folder, score items against your projects.

Imported by build_board.py and ask.py. Not meant to be run on its own, though

    python content_brain.py sample-data

will dump what it read, which is the fastest way to see whether OCR is working.

Reading an image: the tesseract CLI through subprocess, if tesseract is on PATH.
When it is not, the fallback is the filename plus a sidecar text file of the same
stem (foo.png next to foo.txt). The fallback is not a stub, it is the path most
people will actually hit, so it is tested.

Classification is term overlap between the item's text and one line of
projects.md. No model, no network. --ai in build_board.py only gets consulted
for the items local scoring could not place.
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
TEXT_EXTS = {".txt", ".md"}

# Words that are everywhere and therefore tell you nothing about which project
# an item serves.
STOPWORDS = {
    "a", "about", "after", "all", "an", "and", "any", "are", "as", "at", "be",
    "because", "been", "before", "but", "by", "can", "cannot", "did", "do",
    "does", "for", "from", "get", "got", "had", "has", "have", "he", "her",
    "here", "hey", "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "just", "like", "me", "more", "my", "no", "not", "of", "on", "one",
    "only", "or", "out", "over", "post", "saved", "she", "so", "some", "still",
    "that", "the", "their", "them", "then", "there", "they", "this", "to", "up",
    "use", "very", "want", "was", "we", "were", "what", "when", "which", "who",
    "why", "will", "with", "would", "you", "your",
}

# An item that reads like someone asking you something. The question mark is the
# strongest signal; the rest catch the DM-shaped ones that forgot it.
ASK_PATTERNS = (
    r"\?",
    r"\bthoughts\b",
    r"\bdm from\b",
    r"\bcan you\b",
    r"\bcould you\b",
    r"\bdo you\b",
    r"\bdid you\b",
    r"\bwould you\b",
    r"\bany chance\b",
    r"\blet me know\b",
)

# OCR invents long dashes, curly quotes and ellipses. Flattened on the way out
# so the board stays plain and diffs cleanly. Written as code points on purpose:
# the characters themselves are not allowed in this repo's source.
FANCY = {
    0x2014: "-", 0x2013: "-",          # em dash, en dash
    0x2018: "'", 0x2019: "'",          # curly single quotes
    0x201C: '"', 0x201D: '"',          # curly double quotes
    0x2026: "...",                     # ellipsis
}

MIN_SCORE = 2.0        # below this, an item is unfiled
AMBIGUOUS_GAP = 1.0    # top two projects this close means the local call is a guess


@dataclass
class Project:
    name: str
    terms: list[str]


@dataclass
class Item:
    path: str
    text: str
    source: str                       # "ocr", "sidecar", "filename", or "text"
    project: str = "unfiled"
    score: float = 0.0
    matched: list[str] = field(default_factory=list)
    asks: bool = False
    ambiguous: bool = False

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def excerpt(self, limit: int = 110) -> str:
        flat = self.text.translate(FANCY)
        flat = re.sub(r"\s+", " ", flat).strip()
        return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "..."


# --- reading projects.md -----------------------------------------------------

def load_projects(path: str) -> list[Project]:
    """One project per line: 'Name: term, term, term'. Headings are skipped."""
    projects = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            name, _, rest = line.partition(":")
            terms = [t.strip().lower() for t in rest.split(",") if t.strip()]
            if terms:
                projects.append(Project(name.strip(), terms))
    return projects


# --- reading the inbox -------------------------------------------------------

def have_tesseract() -> bool:
    return shutil.which("tesseract") is not None


def ocr(path: str) -> str:
    """Run the tesseract CLI and return what it read. Empty string if it fails."""
    try:
        done = subprocess.run(
            ["tesseract", path, "stdout", "--psm", "6"],
            capture_output=True, text=True, errors="replace", timeout=60,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def ocr_ai(path: str) -> str:
    """Optional vision read. Sends the image file's bytes and nothing else.

    Only reached with --ai, a key set, and no usable local OCR. Lazy import so
    the project has no dependency on anthropic for anyone who never calls this.
    """
    import anthropic

    media = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("ascii")
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=600,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": media, "data": data}},
            {"type": "text", "text": "Transcribe every word of text in this "
                                     "image. Output the text only, no commentary."},
        ]}],
    )
    return msg.content[0].text.strip()


def words_from_filename(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[-_.]+", " ", stem)


def sidecar_text(path: str) -> str:
    stem = os.path.splitext(path)[0]
    for ext in TEXT_EXTS:
        if os.path.exists(stem + ext):
            with open(stem + ext, encoding="utf-8", errors="replace") as f:
                return f.read()
    return ""


def read_image(path: str, use_ai: bool = False) -> tuple[str, str]:
    """Return (text, how we got it) for one image."""
    if have_tesseract():
        text = ocr(path)
        if text:
            return text, "ocr"
    if use_ai and os.getenv("ANTHROPIC_API_KEY"):
        try:
            text = ocr_ai(path)
            if text:
                return text, "vision"
        except Exception as e:                       # noqa: BLE001
            print(f"  (vision read failed on {os.path.basename(path)}: {e})")
    side = sidecar_text(path)
    if side.strip():
        return words_from_filename(path) + "\n" + side, "sidecar"
    return words_from_filename(path), "filename"


def load_items(folder: str, use_ai: bool = False) -> list[Item]:
    """Every image, plus every text file that is not some image's sidecar."""
    items = []
    names = sorted(os.listdir(folder))
    image_stems = {os.path.splitext(n)[0] for n in names
                   if os.path.splitext(n)[1].lower() in IMAGE_EXTS}
    for name in names:
        path = os.path.join(folder, name)
        stem, ext = os.path.splitext(name)
        ext = ext.lower()
        if ext in IMAGE_EXTS:
            text, source = read_image(path, use_ai)
            items.append(Item(path, text, source))
        elif ext in TEXT_EXTS and stem not in image_stems:
            with open(path, encoding="utf-8", errors="replace") as f:
                items.append(Item(path, f.read(), "text"))
    return items


# --- scoring -----------------------------------------------------------------

def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']{3,}|\d+", text.lower())
            if w not in STOPWORDS}


def score_against(text: str, project: Project) -> tuple[float, list[str]]:
    """Term overlap. A multi-word term that appears as a phrase counts double,
    because 'cast iron' matching as a phrase means far more than 'iron' alone."""
    low = " " + re.sub(r"[^a-z0-9 ]+", " ", text.lower()) + " "
    item_tokens = tokens(text)
    total, matched = 0.0, []
    for term in project.terms:
        if " " in term:
            if term in low:
                total += 2.0
                matched.append(term)
        elif term in item_tokens:
            total += 1.0
            matched.append(term)
    return total, matched


def looks_like_a_question(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in ASK_PATTERNS)


def classify(items: list[Item], projects: list[Project]) -> list[Item]:
    for item in items:
        ranked = []
        for p in projects:
            s, matched = score_against(item.text, p)
            ranked.append((s, p.name, matched))
        ranked.sort(key=lambda r: -r[0])
        best = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
        item.asks = looks_like_a_question(item.text)
        if best[0] >= MIN_SCORE:
            item.project, item.score, item.matched = best[1], best[0], best[2]
            item.ambiguous = (best[0] - runner_up) < AMBIGUOUS_GAP
        else:
            item.project, item.score, item.matched = "unfiled", best[0], best[2]
            item.ambiguous = best[0] > 0
    return items


def search(items: list[Item], query: str) -> list[tuple[float, Item]]:
    """Rank items by how much of the query they contain. Phrase hit counts most."""
    q_tokens = tokens(query)
    phrase = re.sub(r"\s+", " ", query.lower()).strip()
    hits = []
    for item in items:
        low = re.sub(r"[^a-z0-9 ]+", " ", item.text.lower())
        low = re.sub(r"\s+", " ", low)
        overlap = len(q_tokens & tokens(item.text))
        if not overlap:
            continue
        s = float(overlap) / max(len(q_tokens), 1)
        if " " in phrase and phrase in low:
            s += 1.0
        hits.append((s, item))
    return sorted(hits, key=lambda h: (-h[0], h[1].name))


def main() -> None:
    ap = argparse.ArgumentParser(description="dump what the reader got out of a folder")
    ap.add_argument("folder", nargs="?", default="sample-data")
    args = ap.parse_args()
    print("tesseract:", "found" if have_tesseract() else "not found (fallback path)")
    for item in load_items(args.folder):
        print(f"\n{item.name}  [{item.source}]\n  {item.excerpt(200)}")


if __name__ == "__main__":
    main()
