# 01: Content Brain

Dump every screenshot, saved post and half-finished note into one folder, run one
command, and get a board that says which of your own projects each thing serves.
It reads the text out of your images with OCR, scores that text against your
project list, and separates out the ones where somebody is waiting on a reply.
Runs on your machine, on your folder, with no key.

| Difficulty | Time | Suggested stack |
|---|---|---|
| Medium | 4-6 hours | Python (standard library), tesseract CLI, Anthropic API (optional) |

## What you'll build

Three small scripts. `make_samples.py` renders text into real PNGs with nothing
but `zlib` and `struct`, so you have screenshots to test on. `build_board.py`
reads the folder, OCRs every image, scores every item against `projects.md`, and
writes `board.md` with a section per project plus "Replies you owe" and
"Unfiled". `ask.py` searches the pile from the terminal. The concept this teaches
is vision plus OCR: getting words out of pixels, then treating those words as
data like any other.

## What you'll learn

- Calling an external CLI tool as a library: `subprocess` around `tesseract`
- Designing for the degraded case, so the tool still works when OCR is missing
- Writing a valid PNG by hand: signature, IHDR, IDAT scanlines, IEND, CRCs
- Why OCR output is noisy and why term-overlap scoring tolerates that noise
- Classifying against a list the user wrote, not a list you invented
- The partition rule: every input lands in exactly one bucket, and you assert it

## Prerequisites

- Python 3.10+ (no pip installs required)
- `tesseract` for the OCR path: `brew install tesseract`. Skip it and the
  fallback path takes over, which is a path you should try on purpose anyway.
- Optional: an Anthropic API key, for close-call classification and for reading
  images on a machine with no tesseract

## Local vs API

| Part | Runs where |
|---|---|
| Walking the folder, reading `.txt` notes | 100% local |
| Reading text out of images (default) | 100% local, `tesseract` CLI via `subprocess` |
| Reading text out of images (no tesseract, no key) | 100% local, filename + sidecar `.txt` |
| Reading text out of images (no tesseract, `--ai` + key) | Claude vision: the image file's own bytes, base64, and one fixed "transcribe this" instruction. Nothing else. Not the filename, not the folder, not your `projects.md`, not any other image. |
| Scoring items against `projects.md` | 100% local |
| "Replies you owe" detection | 100% local, regex |
| Close-call classification with `--ai` | Claude API: your project *names* plus the text of only the items local scoring was unsure about |
| `ask.py` search | 100% local, always, with or without a key |

Sorting and search are local, full stop: `ask.py` has no network code in it, and
`build_board.py` without `--ai` makes no request. Image reading is local via
tesseract by default. The only way a pixel leaves your machine is if tesseract is
missing **and** you pass `--ai` **and** a key is set, and in that case what gets
uploaded is the image file itself and nothing around it.

## How it works

```
sample-data/  (screenshots + notes)
   |
   |-- .png  --> tesseract CLI --> text        (or sidecar .txt if absent)
   |-- .txt  --> text
   |
   v
projects.md  (one project per line: name + terms)
   |
   v  score = term overlap, phrase match counts double
   |
   |-- looks like a question?  --> "Replies you owe"
   |-- best score >= 2         --> that project's section
   |-- otherwise              --> "Unfiled"
   v
board.md         ask.py "budgeting video"
```

## Build it

### Step 1: Make yourself some screenshots

```
python make_samples.py --check
```

This renders five PNGs from a hand-built 5x7 bitmap font, writes a matching
`.txt` sidecar for each, then runs tesseract on every one and prints how many
words came back. You should see 78% to 95% per image. That number is the whole
point of `--check`: if you change the font or the scale, you find out instantly.

### Step 2: Build the board

```
python build_board.py
cat board.md
```

Ten items in, ten items out: two replies owed, six filed under three projects,
two unfiled. `build_board.py` refuses to write a board where an item is missing
or listed twice.

### Step 3: Make it yours

Open `projects.md` and replace it with your actual projects, one per line, in the
form `Name: terms, that, describe, it`. Write the terms the way you talk, not the
way a taxonomy would. Then point the tool at your real folder:

```
python build_board.py --folder ~/Desktop/inbox
```

### Step 4: Search the pile

```
python ask.py "budgeting video"
python ask.py "tesseract ocr" --top 3
```

Ranked matches, each tagged with the project it belongs to, or `reply owed`.

### Step 5: Try the fallback, then the optional AI pass

Hide tesseract and rerun, to see the path a machine without it takes:

```
PATH=/usr/bin:/bin python build_board.py
```

Every image now reads `sidecar` instead of `ocr`, and the groupings barely move.
Then, if you want Claude to break the ties the local scorer flagged as close:

```
export ANTHROPIC_API_KEY=sk-ant-...
python build_board.py --ai
```

## Verify it works

- [ ] `python make_samples.py --check` reports at least 75% of words read back on every PNG
- [ ] `python build_board.py` prints `10 items, 6 filed, 2 replies owed, 2 unfiled`
- [ ] `board.md` has a "Replies you owe" section holding the Mara DM and Sam's note
- [ ] `screenshot-random-poster.png` and `note-ferry-dream.txt` land in "Unfiled"
- [ ] `python ask.py "budgeting video"` returns 3 matches, the envelope note first
- [ ] `PATH=/usr/bin:/bin python build_board.py` still writes a board, sourced `sidecar`
- [ ] `python build_board.py --ai` with no key says so and stays local
- [ ] Running `build_board.py` twice produces a byte-identical `board.md`

## Extend it

- Score against a project's past captions instead of a hand-written term list
- Add a `--since` flag using file mtime, so the board is only this week's intake
- Detect near-duplicate saves (you screenshot the same post twice, often)
- Let an item serve two projects, with a confidence number on each
- Write `board.html` with the thumbnails inline, so you can see what you saved
- Replace the bitmap font with a real TTF renderer and generate harder test images

## Common pitfalls

- **Everything lands in Unfiled**: your `projects.md` terms do not appear in the
  items. Read a few excerpts from `board.md` and steal the words it shows you.
  That is the tuning loop, and it is supposed to take a couple of passes.
- **OCR returns nonsense**: tesseract wants big, high-contrast, roughly
  horizontal text. Phone screenshots are fine; a photo of a screen at an angle is
  not. Try `--psm 6` versus `--psm 11` on one file before blaming the code.
- **OCR typos break your keywords**: they will. `KEY` comes back as `REY`, `N`
  as `M`. Term overlap survives this because one missed word out of twenty does
  not change the ranking. Exact-match rules would not survive it.
- **A sidecar hides a note**: `foo.txt` next to `foo.png` is treated as that
  image's sidecar, not as a note of its own. Name standalone notes something no
  image shares.
- **Replies you owe is greedy**: any `?` sends an item there, ahead of its
  project. That is deliberate, a reply is more urgent than a filing. Trim
  `ASK_PATTERNS` if your notes are full of rhetorical questions.
- **Sending an image to the API by accident**: it cannot happen without `--ai`,
  and even with `--ai` the vision read only fires when tesseract is unavailable.

## Made by

[@qendresahhoti](https://instagram.com/qendresahhoti) on Instagram, [@qbuilder](https://tiktok.com/@qbuilder) on TikTok.
