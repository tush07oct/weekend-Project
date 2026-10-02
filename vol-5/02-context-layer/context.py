"""Context Layer, step 3: assemble one context block for any assistant.

    python context.py work
    python context.py money --memory 5 --copy
    python context.py work --root sample-data/rooms-filled
    python context.py --list

Takes profile.md + rules.md + one room + the most recent dated corrections and
prints a single block you paste at the top of a new conversation. One room at a
time, on purpose: an assistant helping with work does not need your family file.

Prints to stdout. --copy pipes it to pbcopy on macOS and says so if that is not
available. Nothing is uploaded by this script.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

import memory

ROOM_NAMES = ["work", "content", "family", "money"]


def read(path: str) -> str:
    """File contents with the HTML comments and the H1 stripped, or ""."""
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        body = f.read()
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"^# .*$", "", body, count=1, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def shift(block: str) -> str:
    """Push every heading down one level so the assembled block has one H1."""
    return re.sub(r"^(#+ )", r"#\1", block, flags=re.M)


def pick(root: str, home: str, name: str) -> str:
    """Prefer the file in root, fall back to the one next to the script."""
    primary = os.path.join(root, name)
    return primary if os.path.exists(primary) else os.path.join(home, name)


def assemble(root: str, home: str, room: str, n: int) -> str:
    profile = read(pick(root, home, "profile.md"))
    rules = read(pick(root, home, "rules.md"))
    room_path = os.path.join(root, "rooms", f"{room}.md")
    room_body = read(room_path)
    if not room_body:
        raise SystemExit(f"No room file at {room_path}. Run: python init.py --demo")
    entries = memory.recent(memory.parse(pick(root, home, "memory.md")), n, room)

    out = [f"# Context for {room}", ""]
    out += ["## Who I am", "", shift(profile) or "_(no profile yet)_", ""]
    out += ["## How to work with me", "", shift(rules) or "_(no rules yet)_", ""]
    out += [f"## Room: {room}", "", shift(room_body), ""]
    out += ["## Recent corrections", ""]
    if entries:
        out += [f"- {e['date']}: {e['text']}" for e in entries]
    else:
        out.append("_(none yet)_")
    out += ["", "## How to use this", "",
            "Treat the above as background, not as a task. Follow the rules and the "
            "corrections even when I forget to restate them. Ask before assuming "
            "anything the files do not say."]
    return "\n".join(out).rstrip() + "\n"


def copy_to_clipboard(text: str) -> bool:
    """True if the text reached the system clipboard."""
    try:
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Assemble a context block for one room.")
    ap.add_argument("room", nargs="?", help=f"one of: {', '.join(ROOM_NAMES)}")
    ap.add_argument("--memory", type=int, default=8, metavar="N",
                    help="how many recent corrections to include (default 8, 0 for all)")
    ap.add_argument("--root", help="read a different context layer, e.g. sample-data/rooms-filled")
    ap.add_argument("--copy", action="store_true", help="also copy to the clipboard (macOS)")
    ap.add_argument("--list", action="store_true", help="list available rooms and exit")
    args = ap.parse_args()

    home = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(args.root) if args.root else home
    rooms_dir = os.path.join(root, "rooms")

    if args.list:
        print(f"Rooms in {rooms_dir}:")
        for name in ROOM_NAMES:
            path = os.path.join(rooms_dir, f"{name}.md")
            if not os.path.exists(path):
                state = "missing"
            else:
                state = "empty" if "not filled yet" in read(path) else "filled"
            print(f"  {name:8} {state}")
        return

    if not args.room:
        ap.error("name a room, for example: python context.py work (or pass --list)")

    if args.room not in ROOM_NAMES:
        ap.error(f"unknown room '{args.room}'. Choose from: {', '.join(ROOM_NAMES)}")

    block = assemble(root, home, args.room, args.memory)
    sys.stdout.write(block)

    if args.copy:
        ok = copy_to_clipboard(block)
        msg = "Copied to clipboard." if ok else "No pbcopy here, so the block is above only."
        print(f"\n--- {len(block)} characters. {msg}", file=sys.stderr)


if __name__ == "__main__":
    main()
