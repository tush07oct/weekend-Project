"""Context Layer, step 2: dated corrections.

    python memory.py "I prefer metric units, stop converting"
    python memory.py --list 10
    python memory.py --list 10 --room work

Every correction you would otherwise have to repeat goes here, with the date it
happened. The loader pastes the most recent ones into your context block, so the
assistant learns it once instead of every session.

Appends to memory.md. Nothing is uploaded.
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import date

HEADER = """# Memory

<!-- Dated corrections, newest at the bottom. Appended by memory.py. -->
"""

LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2})(?: \[([^\]]+)\])? (.+)$")


def parse(path: str) -> list[dict]:
    """Read memory.md into a list of {date, room, text}, oldest first."""
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            m = LINE.match(raw.rstrip())
            if m:
                entries.append({"date": m.group(1), "room": m.group(2), "text": m.group(3)})
    return entries


def append(path: str, text: str, room: str | None, when: str) -> str:
    """Append one dated correction. Returns the line as written."""
    tag = f" [{room}]" if room else ""
    line = f"- {when}{tag} {text.strip()}"
    fresh = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if fresh:
            f.write(HEADER)
        f.write(line + "\n")
    return line


def recent(entries: list[dict], n: int, room: str | None = None) -> list[dict]:
    """The last n entries, newest last. A room filter keeps untagged entries too,
    because an untagged correction applies everywhere."""
    if room:
        entries = [e for e in entries if e["room"] in (None, room)]
    return entries[-n:] if n > 0 else entries


def main() -> None:
    ap = argparse.ArgumentParser(description="Append or list dated corrections.")
    ap.add_argument("text", nargs="?", help="the correction, in your own words")
    ap.add_argument("--room", help="tag it to one room: work, content, family, money")
    ap.add_argument("--list", dest="list_n", nargs="?", type=int, const=10, metavar="N",
                    help="list the last N entries (default 10)")
    ap.add_argument("--file", default=None, help="path to memory.md")
    ap.add_argument("--date", default=None, help="override the date (YYYY-MM-DD), for tests")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    path = args.file or os.path.join(here, "memory.md")

    if args.list_n is not None:
        entries = recent(parse(path), args.list_n, args.room)
        if not entries:
            print("No memory yet. Add one:")
            print('  python memory.py "I prefer metric units, stop converting"')
            return
        for e in entries:
            tag = f" [{e['room']}]" if e["room"] else ""
            print(f"{e['date']}{tag} {e['text']}")
        return

    if not args.text:
        ap.error("give a correction to record, or pass --list")

    line = append(path, args.text, args.room, args.date or date.today().isoformat())
    total = len(parse(path))
    print(f"Added to {os.path.relpath(path, here)}: {line}")
    print(f"{total} correction(s) on file.")


if __name__ == "__main__":
    main()
