"""Nutrition Lens, a photo or a list of foods in, what to DO about it out.

    python lens.py --foods "spinach, lentils, black tea"
    python lens.py --foods "lentils 200g, bell pepper, brown rice"
    python lens.py sample-data/plate-lentils-tea.png --ai   # needs a key

Typed foods are the default and the fully working path: no key, no install,
no network. The photo path is opt-in. With --ai the image bytes go to the
Anthropic API, Claude names the foods, and the rest of the pipeline is the
same local matching and the same local rules.

Educational project. Not medical advice.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import json
import os
import re
from pathlib import Path

from rules import BUCKETS, amount, apply_rules, totals

HERE = Path(__file__).parent
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

VISION_PROMPT = (
    "Name the foods and drinks visible in this photo of a meal. "
    "Return one lowercase comma-separated line and nothing else, no counts, no "
    "sentences, no markdown. Use plain names a recipe would use, for example: "
    "lentils, spinach, black tea. If the photo is a label or a product, name the "
    "food the product is."
)


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def singular(text: str) -> str:
    """Enough plural handling for food names, no library needed."""
    for suffix, cut in (("ies", 3), ("oes", 2), ("ses", 2), ("shes", 2), ("s", 1)):
        if text.endswith(suffix) and len(text) - cut >= 3:
            stem = text[: len(text) - cut]
            return stem + "y" if suffix == "ies" else stem
    return text


def build_index(db: dict) -> dict[str, dict]:
    """Every name and alias, normalized and singularized, pointing at its food."""
    index: dict[str, dict] = {}
    for food in db["foods"]:
        for key in [food["name"], *food.get("aliases", [])]:
            for variant in (normalize(key), singular(normalize(key))):
                index.setdefault(variant, food)
    return index


def parse_phrase(phrase: str) -> tuple[str, float | None]:
    """'lentils 200g' -> ('lentils', 200.0). '2 eggs' -> ('eggs', None)."""
    grams = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gram|grams)\b", phrase, re.I)
    if m:
        grams = float(m.group(1))
        phrase = phrase[: m.start()] + phrase[m.end():]
    return normalize(re.sub(r"^\s*\d+\s+", "", phrase)), grams


def match_food(phrase: str, index: dict[str, dict]) -> dict | None:
    """Exact, then longest contained alias, then fuzzy. Standard library only."""
    if not phrase:
        return None
    for candidate in (phrase, singular(phrase)):
        if candidate in index:
            return index[candidate]

    words = set(phrase.split()) | {singular(w) for w in phrase.split()}
    contained = [k for k in index if k in phrase or (" " not in k and k in words)]
    if contained:
        return index[max(contained, key=len)]

    close = difflib.get_close_matches(phrase, list(index), n=1, cutoff=0.78)
    if close:
        return index[close[0]]
    return None


def match_meal(foods_text: str, db: dict) -> tuple[list[dict], list[str]]:
    index = build_index(db)
    items: list[dict] = []
    misses: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[,;\n]+|\band\b", foods_text):
        raw = raw.strip()
        if not raw:
            continue
        phrase, grams = parse_phrase(raw)
        food = match_food(phrase, index)
        if food is None:
            misses.append(raw)
            continue
        if food["name"] in seen:
            continue
        seen.add(food["name"])
        items.append({"typed": raw, "food": food, "grams": grams or food["portion_g"]})
    return items, misses


def foods_from_photo(image_path: Path) -> str:
    """The only function that touches the network. Nothing else sends bytes."""
    import anthropic

    suffix = image_path.suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise ValueError(f"unsupported image type {suffix}, use one of {sorted(MEDIA_TYPES)}")
    data = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-5",
        max_tokens=300,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": MEDIA_TYPES[suffix], "data": data}},
            {"type": "text", "text": VISION_PROMPT},
        ]}],
    )
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def sidecar_foods(image_path: Path) -> str | None:
    """Each sample image ships a .txt naming its foods, so the no-key path works."""
    sidecar = image_path.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8").strip()
    return None


def render(items: list[dict], misses: list[str], actions: list[tuple[str, str]], source: str) -> str:
    t = totals(items)
    out = ["", "NUTRITION LENS", f"source: {source}", ""]

    out.append("ON THE PLATE")
    for i in items:
        f = i["food"]
        tag = {"heme": "animal", "non-heme": "plant", "none": "none"}[f["iron_type"]]
        out.append(
            f"  {f['name']:<28} {i['grams']:>5.0f} g   "
            f"iron {amount(i, 'iron_mg'):>5.1f} mg {tag:<7}"
            f"calcium {amount(i, 'calcium_mg'):>5.0f} mg   "
            f"vit C {amount(i, 'vitamin_c_mg'):>5.0f} mg"
        )
    if misses:
        out.append(f"  not in the database, skipped: {', '.join(misses)}")
    out.append("")
    out.append(
        f"MEAL TOTAL   iron {t['iron_mg']:.1f} mg "
        f"({t['iron_nonheme_mg']:.1f} plant / {t['iron_heme_mg']:.1f} animal)   "
        f"calcium {t['calcium_mg']:.0f} mg   vit C {t['vitamin_c_mg']:.0f} mg   "
        f"caffeine {t['caffeine_mg']:.0f} mg"
    )
    out.append("")

    out.append("WHAT TO DO")
    if not actions:
        out.append("  Nothing to change. Eat it.")
    for bucket in BUCKETS:
        lines = [text for b, text in actions if b == bucket]
        for n, text in enumerate(lines, 1):
            label = f"{bucket} {n}" if len(lines) > 1 else bucket
            wrapped = wrap(text, 76, indent=" " * 10)
            out.append(f"  {label:<7} {wrapped.lstrip()}")
            out.append("")
    out.append("Educational project, directional guidance only. Not medical advice.")
    out.append("")
    return "\n".join(out)


def wrap(text: str, width: int, indent: str) -> str:
    words, lines, line = text.split(), [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    return ("\n" + indent).join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="A photo or a food list in, what to do about it out.")
    ap.add_argument("image", nargs="?", help="optional photo; read its .txt sidecar unless --ai")
    ap.add_argument("--foods", help='comma-separated foods, e.g. "spinach, lentils, black tea"')
    ap.add_argument("--ai", action="store_true",
                    help="send the image to the Anthropic API to identify the foods")
    ap.add_argument("--profile", default=str(HERE / "profile.json"))
    ap.add_argument("--db", default=str(HERE / "foods.json"))
    args = ap.parse_args()

    db = load_json(Path(args.db))
    profile = load_json(Path(args.profile))

    if args.foods:
        foods_text, source = args.foods, "typed foods"
    elif args.image:
        image_path = Path(args.image)
        if args.ai and os.getenv("ANTHROPIC_API_KEY"):
            try:
                foods_text, source = foods_from_photo(image_path), f"{image_path.name} via Claude"
            except Exception as exc:
                print(f"(vision call failed: {exc}; falling back to the sidecar)")
                foods_text, source = sidecar_foods(image_path), f"{image_path.name} sidecar"
        else:
            if args.ai:
                print("(--ai needs ANTHROPIC_API_KEY; falling back to the sidecar)")
            foods_text, source = sidecar_foods(image_path), f"{image_path.name} sidecar"
        if not foods_text:
            ap.error(f"no foods found for {args.image}: pass --foods, or add a .txt sidecar")
        print(f"foods read: {foods_text}")
    else:
        ap.error('pass --foods "..." or an image path')

    items, misses = match_meal(foods_text, db)
    if not items:
        ap.error(f"nothing matched the database in: {foods_text}")
    print(render(items, misses, apply_rules(items, db, profile), source))


if __name__ == "__main__":
    main()
