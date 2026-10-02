"""Content Brain, search. Ask the pile a question, get the matching items back.

    python ask.py "budgeting video"
    python ask.py "tesseract" --folder ~/inbox --top 3

Ranked by how much of your query each item contains, with the project each one
belongs to. Reads the folder fresh every time, so it never goes stale against
board.md. Fully local, no key, no network.
"""

from __future__ import annotations

import argparse

from content_brain import classify, have_tesseract, load_items, load_projects, search


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--folder", default="sample-data")
    ap.add_argument("--projects", default="projects.md")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    projects = load_projects(args.projects)
    items = classify(load_items(args.folder), projects)
    hits = search(items, args.query)

    if not have_tesseract():
        print("(tesseract not found, images read from filename + sidecar)\n")
    if not hits:
        print(f'Nothing matched "{args.query}". '
              f"Searched {len(items)} items in {args.folder}.")
        return

    print(f'{len(hits)} match(es) for "{args.query}":\n')
    for rank, (sc, item) in enumerate(hits[: args.top], 1):
        tag = "reply owed" if item.asks else item.project
        print(f"{rank}. {item.name}  [{tag}]  match {sc:.2f}")
        print(f"   {item.excerpt(140)}\n")
    if len(hits) > args.top:
        print(f"...{len(hits) - args.top} more, pass --top {len(hits)} to see them.")


if __name__ == "__main__":
    main()
