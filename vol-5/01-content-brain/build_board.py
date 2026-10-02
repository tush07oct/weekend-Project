"""Content Brain, build the board. Screenshots and notes in, one board.md out.

    python build_board.py                       # reads sample-data/ and projects.md
    python build_board.py --folder ~/inbox      # your real pile
    python build_board.py --ai                  # Claude decides the close calls

Writes board.md: every item grouped under the project it serves, plus "Replies
you owe" for the ones that look like a question, and "Unfiled" for the ones
nothing matched. Every input item appears exactly once, and the script checks
that before it writes.

Fully local by default. --ai needs ANTHROPIC_API_KEY and only sends the items
local scoring could not place.
"""

from __future__ import annotations

import argparse
import os

from content_brain import (
    Item, Project, classify, have_tesseract, load_items, load_projects,
)


def resolve_ambiguous_ai(items: list[Item], projects: list[Project]) -> int:
    """Ask Claude to place the items local scoring was unsure about.

    Sends the project names and the text of those items only. Lazy import, and
    any failure leaves the local answer in place.
    """
    import anthropic

    unsure = [i for i in items if i.ambiguous]
    if not unsure:
        return 0
    names = [p.name for p in projects]
    listing = "\n\n".join(
        f"[{n}] {i.name}\n{i.excerpt(400)}" for n, i in enumerate(unsure))
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=800,
        messages=[{"role": "user", "content": (
            "My projects:\n" + "\n".join(f"- {n}" for n in names) +
            "\n\nEach item below is something I saved. Say which single project "
            "it serves, or 'unfiled' if none of them do.\n"
            "Return one line per item, exactly 'index: project name', nothing else.\n\n"
            + listing
        )}],
    )
    changed = 0
    for line in msg.content[0].text.splitlines():
        idx, _, label = line.partition(":")
        label = label.strip()
        try:
            item = unsure[int(idx.strip().strip("[]"))]
        except (ValueError, IndexError):
            continue
        match = next((n for n in names if n.lower() == label.lower()), None)
        if match and match != item.project:
            item.project, item.matched = match, ["claude"]
            changed += 1
        elif label.lower() == "unfiled" and item.project != "unfiled":
            item.project, item.matched = "unfiled", ["claude"]
            changed += 1
    return changed


def render(items: list[Item], projects: list[Project], folder: str) -> str:
    owed = [i for i in items if i.asks]
    rest = [i for i in items if not i.asks]

    out = ["# Content Brain board\n",
           f"{len(items)} items read from `{folder}`. "
           f"{len(owed)} look like someone asked you something.\n"]

    out.append("## Replies you owe\n")
    if owed:
        for i in sorted(owed, key=lambda x: x.name):
            where = i.project if i.project != "unfiled" else "no project yet"
            out.append(f"- **{i.name}** ({where}) `{i.source}`  \n  {i.excerpt()}")
    else:
        out.append("- Nothing. Enjoy it.")
    out.append("")

    for p in projects:
        mine = sorted((i for i in rest if i.project == p.name), key=lambda x: x.name)
        if not mine:
            continue
        out.append(f"## {p.name}\n")
        for i in mine:
            hits = ", ".join(i.matched[:5]) or "no terms"
            out.append(f"- **{i.name}** `{i.source}` score {i.score:.0f} "
                       f"({hits})  \n  {i.excerpt()}")
        out.append("")

    unfiled = sorted((i for i in rest if i.project == "unfiled"), key=lambda x: x.name)
    out.append("## Unfiled\n")
    if unfiled:
        out.append("Nothing scored high enough. Either it is not for a project "
                   "yet, or projects.md needs the word for it.\n")
        for i in unfiled:
            out.append(f"- **{i.name}** `{i.source}` best score {i.score:.0f}  \n"
                       f"  {i.excerpt()}")
    else:
        out.append("- Empty. Every item found a home.")
    return "\n".join(out) + "\n"


def check_each_item_once(items: list[Item], board: str) -> None:
    missing = [i.name for i in items if i.name not in board]
    if missing:
        raise SystemExit(f"bug: these items did not make it onto the board: {missing}")
    doubled = [i.name for i in items if board.count(i.name) != 1]
    if doubled:
        raise SystemExit(f"bug: these items appear more than once: {doubled}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="sample-data")
    ap.add_argument("--projects", default="projects.md")
    ap.add_argument("--out", default="board.md")
    ap.add_argument("--ai", action="store_true",
                    help="let Claude place the items local scoring was unsure about")
    args = ap.parse_args()

    projects = load_projects(args.projects)
    if not projects:
        raise SystemExit(f"no projects found in {args.projects}")

    print("Reading images with:",
          "tesseract" if have_tesseract() else "filename + sidecar fallback")
    items = classify(load_items(args.folder, use_ai=args.ai), projects)

    if args.ai and os.getenv("ANTHROPIC_API_KEY"):
        try:
            n = resolve_ambiguous_ai(items, projects)
            print(f"Claude re-placed {n} close call(s)")
        except Exception as e:                       # noqa: BLE001
            print(f"(AI pass failed: {e}; keeping the local answers)")
    elif args.ai:
        print("(--ai passed but ANTHROPIC_API_KEY is not set; staying local)")

    board = render(items, projects, args.folder)
    check_each_item_once(items, board)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(board)

    filed = sum(1 for i in items if i.project != "unfiled" and not i.asks)
    owed = sum(1 for i in items if i.asks)
    print(f"Wrote {args.out}: {len(items)} items, {filed} filed, "
          f"{owed} replies owed, {len(items) - filed - owed} unfiled")


if __name__ == "__main__":
    main()
