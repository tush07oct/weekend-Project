# 03: Nutrition Lens

Type what is on your plate, or point it at a photo, and get back what to DO
about it: the pairing to add, the drink to move an hour later, the thing that is
quietly blocking absorption. Not a nutrient dump. It runs on your machine, on a
nutrition database you can open in a text editor.

**This is an educational project. It is not medical advice, and `foods.json` is
a small hand-authored teaching slice, not a clinical reference. Nothing here is
a reason to change how you eat or what you take without talking to a clinician.**

| Difficulty | Time | Suggested stack |
|---|---|---|
| Medium | 4-6 hours | Python (standard library), Anthropic API (optional) |

## What you'll build

A local pipeline with three clean stages: something names the foods, a fuzzy
matcher pins each name to a row in a bundled nutrition database, and a rules
layer reads your profile and prints imperatives. The naming stage is pluggable,
which is the whole point: typed text by default, a vision model behind `--ai`
when you want it. Everything downstream is identical either way.

## What you'll learn

- Vision as one swappable stage, not the architecture: the model names things, your code decides things
- Fuzzy matching free text to a fixed vocabulary with `difflib` and a little plural handling
- Separating data (`foods.json`), personalization (`profile.json`) and logic (`rules.py`)
- Writing a rules layer that outputs actions, not facts, and that stays honest about effect sizes
- Writing a valid PNG from scratch with `zlib` and `struct`, no image library

## Prerequisites

- Python 3.10+ (no pip installs required for the default path)
- A meal you can describe in words. The repo ships two sample plates to start.
- Optional: an Anthropic API key, only if you want the `--ai` photo path

## Local vs API

| Part | Runs where |
|---|---|
| Typing the foods (`--foods`) | 100% local |
| Reading a sample image's `.txt` sidecar | 100% local |
| The nutrition database (`foods.json`) | 100% local, never sent anywhere |
| Your profile (`profile.json`: concerns, goals, pantry, supplements) | 100% local, never sent anywhere |
| Matching foods to database rows | 100% local |
| The rules layer and every number printed | 100% local |
| Naming the foods in a photo with `--ai` | Claude API (only if you pass `--ai` **and** set a key) |

Be precise about the photo, because it is the only interesting byte here. By
default the photo is **never opened by a network call at all**: `lens.py` reads
the `.txt` sidecar next to it and nothing leaves the machine. When you pass
`--ai`, the image bytes of that one file are base64'd and sent to the Anthropic
API, and **nothing else is**. The nutrition database, your profile, your
concerns, your supplement list, and every rule that fires stay on your machine
in both cases. What comes back from the API is a comma-separated list of food
names, which then goes through exactly the same local matcher as text you typed.

## How it works

```
photo.png                     --foods "spinach, lentils, black tea"
   ↓  --ai: base64 → Claude            ↓
   ↓  default: read photo.txt          ↓
        "spinach, lentils, black tea"  ←
   ↓  match (difflib + alias table) against foods.json
items: name, grams, iron / calcium / vitamin C / caffeine
   ↓  totals + profile.json (low iron, pantry, supplements)
   ↓  rules.py
ADD  ... pairing to add
MOVE ... timing to change
KNOW ... what is blocking absorption
```

## Build it

### Step 1: Run it on a plate that has a problem

```
python lens.py --foods "spinach, lentils, black tea"
```

You get the per-food numbers, then a `MOVE` telling you to drink the tea an hour
later, an `ADD` naming a vitamin C food from your pantry, and a `KNOW` warning
you not to trust spinach's iron number.

### Step 2: Run it on a plate that does not

```
python lens.py --foods "chicken breast, bell pepper, white rice, broccoli"
```

No `MOVE` at all, and the vitamin C rule flips from "add some" to "keep it".
A rules layer that only ever scolds you is a rules layer you stop reading.

### Step 3: Read `foods.json`, then break it

Every row is per 100 g, plus a `portion_g` default and an alias list. The
interesting fields are not the macros: they are `iron_type`, `tannin_level`,
`phytate_level`, `oxalate_level`, and the `thresholds` block at the top. Change
`calcium_inhibits_mg` and watch which meals start getting a `MOVE`.

### Step 4: Make it yours in `profile.json`

`concerns`, `pantry`, and `habits.supplements` all change the output. The pantry
is what turns a generic "eat more vitamin C" into "add the bell pepper you
already have", which is the difference between advice and an instruction.

### Step 5: Turn on the photo path (optional)

```
python make_samples.py                     # regenerates sample-data/, already committed
python lens.py sample-data/plate-lentils-tea.png            # local, reads the sidecar
export ANTHROPIC_API_KEY=sk-ant-...
python lens.py sample-data/plate-lentils-tea.png --ai       # sends the image bytes
```

The sample PNGs are labelled colour blocks, written by `make_samples.py` with
`zlib` and `struct` because there is no image library here. They exist to
exercise the `--ai` path and to stand in for a real photo. Point `--ai` at a
real photo of your own dinner and the rest of the pipeline does not change.

## Verify it works

- [ ] `python lens.py --foods "spinach, lentils, black tea"` prints a `MOVE` about the tea and an `ADD` naming bell pepper
- [ ] `python lens.py --foods "chicken breast, bell pepper, white rice, broccoli"` prints no `MOVE` lines
- [ ] `python lens.py --foods "strawberrys, cofee, greek yoghurt"` still matches all three despite the typos and the plural
- [ ] `python make_samples.py` writes two PNGs and two `.txt` sidecars into `sample-data/`
- [ ] `python lens.py sample-data/plate-chicken-pepper.png` works with no API key, echoing `foods read: ...` from the sidecar
- [ ] `python lens.py --foods "pizza, fries"` exits with a clear "nothing matched" error instead of a traceback

## Extend it

- Add a `--day` mode: several meals at once, so the rules can say "move the tea to 3pm, you already have a gap there"
- Add vitamin D, zinc and B12, each with its own enhancer and inhibitor pairs
- Add portion estimation to the `--ai` prompt and compare it against the `portion_g` defaults
- Let `profile.json` carry a blood panel date so the output can say "retest in 8 weeks"
- Swap the printed report for a tiny HTML page, the way vol-3's Money Map does

## Common pitfalls

- **Everything is "not in the database"**: `foods.json` is 43 rows. That is a
  teaching slice, not a food atlas. Add your foods and your aliases; that is the
  expected work, and the alias list is where it happens.
- **The matcher is confidently wrong**: `difflib` at cutoff 0.78 will map
  "unicorn steak" to beef, because "steak" is right there. Check the `ON THE
  PLATE` block before you trust the advice.
- **Treating the numbers as precise**: they are plausible per-100g values for
  teaching the rules. Absorption depends on dose, meal composition and the
  person, which is why the output says "substantially" and never a percentage.
  Resist the urge to add one.
- **Expecting the AI path to be the real one**: it names foods, nothing more.
  Every number and every recommendation comes from your local files, so an AI
  outage downgrades the project to typing, not to broken.
- **Sending a photo by accident**: it only happens with `--ai` and a key set.
  Without both, `lens.py` reads the `.txt` sidecar and opens no socket.

## Made by

[@qendresahhoti](https://instagram.com/qendresahhoti) on Instagram, [@qbuilder](https://tiktok.com/@qbuilder) on TikTok.
