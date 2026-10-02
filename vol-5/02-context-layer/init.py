"""Context Layer, step 1: the guided interview that fills your rooms.

    python init.py --demo                  # fill every room from sample answers
    python init.py                         # interview yourself, interactively
    python init.py --only work             # one room at a time
    python init.py --from sample-data/answers.json --out sample-data/rooms-filled
    python init.py --blank                 # write empty room templates

A "room" is one area of life: work, content, family, money. Each room becomes a
short markdown file you own, shaped so it can be pasted straight into any
assistant as context.

Nothing is uploaded. This script only reads and writes files on your disk.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Each room is a list of (key, heading, question, multi).
# multi=True means "one item per line, blank line to finish" and renders as bullets.
ROOMS: dict[str, dict] = {
    "work": {
        "title": "Work",
        "blurb": "The job. What you are responsible for and what you are stuck on.",
        "questions": [
            ("role", "Role", "In one line: what do you do, and for whom?", False),
            ("focus", "Current focus", "What are you actually working on this month?", True),
            ("projects", "Active projects", "Name each live project and its state.", True),
            ("constraints", "Constraints", "Deadlines, hours, budgets, things you cannot change.", True),
            ("people", "People", "Who you work with. Name, role, why they matter.", True),
            ("vocabulary", "Vocabulary", "Internal terms an outsider would not know.", True),
            ("help", "What good help looks like", "When an assistant helps here, what does good look like?", True),
        ],
    },
    "content": {
        "title": "Content",
        "blurb": "What you publish, for whom, and in what voice.",
        "questions": [
            ("channels", "Channels", "Where do you publish, and how often?", True),
            ("audience", "Audience", "Who is on the other side of the screen?", True),
            ("voice", "Voice rules", "Rules your writing follows. Be specific.", True),
            ("pipeline", "Pipeline", "How an idea becomes a published thing.", True),
            ("banned", "Never do this", "Words, formats, and moves that are off limits.", True),
            ("help", "What good help looks like", "What should an assistant do here without being asked?", True),
        ],
    },
    "family": {
        "title": "Family",
        "blurb": "The people and the weekly shape of your life outside work.",
        "questions": [
            ("household", "Household", "Who lives with you, and where?", True),
            ("people", "People", "Names, ages or roles, one line each.", True),
            ("rhythms", "Weekly rhythms", "Fixed commitments and the shape of a normal week.", True),
            ("care", "Handle with care", "Topics to be gentle or quiet about.", True),
            ("help", "What good help looks like", "What kind of help is actually useful here?", True),
        ],
    },
    "money": {
        "title": "Money",
        "blurb": "How your money is set up and what you are aiming at.",
        "questions": [
            ("setup", "Setup", "Income sources, accounts, who handles what.", True),
            ("goals", "Goals", "What you are saving for or paying down, with numbers.", True),
            ("recurring", "Recurring commitments", "Fixed monthly obligations.", True),
            ("rules", "Rules I follow", "Your own money rules, however odd.", True),
            ("care", "Handle with care", "What you do not want advice about.", True),
            ("help", "What good help looks like", "What should an assistant do with this?", True),
        ],
    },
}

PROFILE = {
    "title": "Profile",
    "blurb": "Who you are. Short, stable facts. Change rarely.",
    "questions": [
        ("name", "Name", "What should an assistant call you?", False),
        ("where", "Where", "City, country, timezone.", False),
        ("work", "What I do", "One line, the version you would say at a party.", False),
        ("facts", "Stable facts", "Things that are true for years, not weeks.", True),
        ("units", "Units and formats", "Units, date format, currency, language.", True),
    ],
}

PLACEHOLDER = "_(not filled yet)_"


def room_spec(name: str) -> dict:
    return PROFILE if name == "profile" else ROOMS[name]


def render(name: str, answers: dict) -> str:
    """Render one room (or the profile) as markdown from an answers dict."""
    spec = room_spec(name)
    out = [f"# {spec['title']}", "", f"<!-- {spec['blurb']} -->", ""]
    for key, heading, _question, multi in spec["questions"]:
        out.append(f"## {heading}")
        value = answers.get(key)
        if multi:
            items = [str(v).strip() for v in (value or []) if str(v).strip()]
            out.extend(f"- {item}" for item in items)
            if not items:
                out.append(PLACEHOLDER)
        else:
            out.append(str(value).strip() if value and str(value).strip() else PLACEHOLDER)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def is_filled(path: str) -> bool:
    """True if the file on disk has real content, not just placeholders."""
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        body = f.read()
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line == PLACEHOLDER:
            continue
        return True
    return False


def ask(spec: dict) -> dict:
    """Interview one room on stdin. Blank line ends a multi-answer list."""
    print(f"\n=== {spec['title']} ===")
    print(spec["blurb"])
    answers: dict = {}
    for key, heading, question, multi in spec["questions"]:
        print(f"\n{heading}: {question}")
        if multi:
            print("  (one per line, empty line when done)")
            items = []
            while True:
                try:
                    line = input("  - ").strip()
                except EOFError:
                    break
                if not line:
                    break
                items.append(line)
            answers[key] = items
        else:
            try:
                answers[key] = input("  > ").strip()
            except EOFError:
                answers[key] = ""
    return answers


def write_room(name: str, answers: dict, out_dir: str, force: bool, assume_yes: bool) -> str | None:
    """Write one room file. Returns the path written, or None if skipped."""
    sub = "" if name == "profile" else "rooms"
    target_dir = os.path.join(out_dir, sub) if sub else out_dir
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, f"{name}.md")

    if is_filled(path) and not force:
        if assume_yes or not sys.stdin.isatty():
            print(f"  skipped {path} (already filled, pass --force to overwrite)")
            return None
        if input(f"  {path} already has content. Overwrite? [y/N] ").strip().lower() != "y":
            print("  skipped")
            return None

    with open(path, "w", encoding="utf-8") as f:
        f.write(render(name, answers))
    print(f"  wrote {path}")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill your context rooms.")
    ap.add_argument("--demo", action="store_true",
                    help="fill from sample-data/answers.json, no typing")
    ap.add_argument("--from", dest="answers_file", help="fill from a JSON answers file")
    ap.add_argument("--blank", action="store_true", help="write empty templates")
    ap.add_argument("--only", action="append", metavar="ROOM",
                    help="limit to one room (repeatable): profile, work, content, family, money")
    ap.add_argument("--out", default=".", help="output directory (default: here)")
    ap.add_argument("--force", action="store_true", help="overwrite rooms that already have content")
    ap.add_argument("-y", "--yes", action="store_true", help="never prompt; skip filled rooms")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    names = ["profile"] + list(ROOMS)
    if args.only:
        unknown = [n for n in args.only if n not in names]
        if unknown:
            ap.error(f"unknown room(s): {', '.join(unknown)}. Choose from: {', '.join(names)}")
        names = [n for n in names if n in args.only]

    source: dict = {}
    if args.blank:
        mode = "blank templates"
    elif args.demo or args.answers_file:
        path = args.answers_file or os.path.join(here, "sample-data", "answers.json")
        with open(path, encoding="utf-8") as f:
            source = json.load(f)
        mode = f"answers from {os.path.relpath(path, here)}"
    else:
        mode = "interactive interview"

    print(f"Context Layer init: {mode}")
    written = 0
    for name in names:
        if mode == "interactive interview":
            answers = ask(room_spec(name))
        else:
            answers = source.get(name, {})
        if write_room(name, answers, args.out, args.force, args.yes):
            written += 1

    print(f"\n{written} of {len(names)} file(s) written. Next:")
    print("  python memory.py \"I prefer metric units, stop converting\"")
    print("  python context.py work")


if __name__ == "__main__":
    main()
