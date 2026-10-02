# 02: Context Layer

Every assistant you talk to starts from zero. This builds the onboarding it
should have gotten: four markdown files about your work, your content, your
family, and your money, plus a dated log of corrections, assembled on demand
into one block you paste at the top of a conversation. Plain files on your disk,
and this project makes no network calls at all.

| Difficulty | Time | Suggested stack |
|---|---|---|
| Easy-Medium | 3-5 hours | Python (standard library only) |

## What you'll build

A personal context system in four parts. `rooms/` holds one short file per area
of life. `init.py` interviews you and fills them. `memory.py` appends dated
corrections so you stop repeating yourself. `context.py work` assembles profile +
rules + that one room + your most recent corrections into a single block, printed
to stdout and optionally copied to the clipboard. No database, no vector store,
no account. If you delete this folder, you have lost markdown files you can
rewrite, which is the whole point.

## What you'll learn

- Context engineering: deciding what an assistant needs to know before it asks
- Scoping context by room, so a work question does not drag in your family file
- Separating stable facts (profile) from preferences (rules) from corrections (memory)
- Why dated, append-only memory beats editing a single "about me" paragraph
- Designing a file to be read by a model: headings, short lines, no prose padding
- Writing a CLI that works interactively and non-interactively from the same code

## Prerequisites

- Python 3.10+ (no pip installs, no API key, nothing to sign up for)
- 20 minutes to answer questions about yourself honestly
- Optional: macOS, for `--copy` to reach the clipboard via `pbcopy`

## Local vs API

| Part | Runs where |
|---|---|
| The interview (`init.py`) | 100% local |
| The room, profile, and rules files | 100% local, plain markdown on your disk |
| Dated corrections (`memory.py`) | 100% local, appended to `memory.md` |
| Assembling the context block (`context.py`) | 100% local |
| `--copy` to the clipboard | 100% local (`pbcopy` subprocess) |

Everything. 100% local. This project makes no network calls, has no API key, and
has no `.env.example` because there is no key to put in it. The only way any of
this text reaches a model is if you paste the assembled block into a chat window
yourself. That is a decision you make per conversation, with the whole block in
front of you.

## How it works

```
you, answering questions
   ↓  init.py  (interactive, or --demo from sample-data/answers.json)
rooms/work.md  rooms/content.md  rooms/family.md  rooms/money.md
profile.md  rules.md
   +
memory.py "stop converting to imperial"  →  memory.md  (dated, append-only)
   ↓  context.py work --memory 8
ONE context block on stdout  →  paste into any assistant  (or --copy)
```

## Build it

### Step 1: See it work before you type anything

```
python context.py work --root sample-data/rooms-filled
```

That is a filled-in context layer for a made-up product designer in Lisbon. Read
the output. It is the shape you are aiming at: headings, one fact per line, no
sentences that could describe anyone else.

### Step 2: Fill your own rooms from the sample, then edit

```
python init.py --demo
python context.py --list
```

`--demo` writes the sample answers into your real `rooms/`, `profile.md` included,
so you can edit real files instead of staring at blanks. Open `rooms/work.md` and
replace a few lines with the truth. Rerun `context.py work` and watch the block
change.

### Step 3: Do the interview properly

```
python init.py --only work
python init.py --only money --only family
```

It asks each question on stdin. Multi-answer questions take one item per line and
end on a blank line. It will not overwrite a room that already has content unless
you pass `--force`, so going room by room over a week is safe.

If you would rather be interviewed by a model than by a prompt loop, use the
interview prompt in `prompts.md` and paste the answers back into the room files.
The files are the product; `init.py` is one way to fill them.

### Step 4: Start logging corrections

```
python memory.py "I prefer metric units, stop converting"
python memory.py "Tomas wants the recommendation in the first line" --room work
python memory.py --list 5
```

The rule: every time you correct an assistant and think "I have said this
before", it goes in here. Untagged corrections apply to every room. A `--room`
tag limits one to that room's block.

### Step 5: Use it, every time

```
python context.py work --memory 8 --copy
```

Paste it as the first message of a new conversation. `--memory N` controls how
many recent corrections ride along; 0 means all of them. When the block stops
matching reality, that is the signal to edit a room file, not to explain it again
in chat.

## Verify it works

- [ ] `python context.py --list` prints four rooms, all `empty` on a fresh clone
- [ ] `python context.py work --root sample-data/rooms-filled` prints a full block ending in "How to use this"
- [ ] `python init.py --demo` writes 5 files, and `python init.py --demo -y` then skips all 5
- [ ] `python init.py --demo --only work --force` rewrites exactly one file
- [ ] `python memory.py "test"` prints the dated line it appended
- [ ] `python memory.py --list 5 --room work` shows work-tagged and untagged entries
- [ ] `python context.py work --memory 3` includes at most 3 corrections
- [ ] `python context.py garage` fails with a list of the real room names

## Extend it

- Add a room: a dict entry in `ROOMS` is the whole change, the rest follows
- A `--format xml` flag, since some models follow tagged sections more closely
- `context.py work content` to merge two rooms when a task genuinely spans both
- A staleness check: flag any room file untouched for 90 days
- Write the block to your editor's rules file (`CLAUDE.md`, `.cursorrules`) instead of the clipboard
- An optional `--ai` polish pass that tightens your room prose, local path staying the default

## Common pitfalls

- **Rooms written as prose**: paragraphs get skimmed by models the same way they
  get skimmed by people. One fact per line, no connective tissue.
- **Everything in one room**: if `work.md` grows past a screen, it is two rooms.
  Split it before it becomes a file nobody updates.
- **Memory as a diary**: it is for corrections you would otherwise repeat, not
  for what happened today. Ten sharp lines beat two hundred soft ones.
- **Rules nobody could break**: "be helpful" is not a rule. "No preamble, no
  closing offer of further help" is, and you can check whether it was followed.
- **Pasting the family room into a work chat**: the room selector is explicit for
  exactly this reason. Read the block before you paste it.
- **Forgetting it is yours**: nothing here is a format anyone else controls. If
  a heading does not help you, delete it.

## Made by

[@qendresahhoti](https://instagram.com/qendresahhoti) on Instagram, [@qbuilder](https://tiktok.com/@qbuilder) on TikTok.
