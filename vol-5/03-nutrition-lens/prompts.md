# Prompts: Nutrition Lens

Without any prompt at all you type the foods and the whole project works:
matching is `difflib` plus an alias table, and the advice is `rules.py`. These
prompts only replace the typing.

## Prompt 1: Name the foods in a photo

This is the one wired into `--ai` in `lens.py`. It is deliberately boring.

```
Name the foods and drinks visible in this photo of a meal. Return one lowercase
comma-separated line and nothing else, no counts, no sentences, no markdown. Use
plain names a recipe would use, for example: lentils, spinach, black tea. If the
photo is a label or a product, name the food the product is.
```

Sent with the image as a base64 block. Nothing else about you goes with it.

## Prompt 2: Suggest aliases for an unmatched food

Use this on whatever landed in the "not in the database, skipped" line. It grows
`foods.json` instead of growing the prompt.

```
I have a nutrition lookup table keyed by food name plus an alias list. These
inputs failed to match any row:
{the skipped strings, one per line}

For each one, return JSON: [{"input": "...", "best_match": "...", "aliases": [...]}]
- best_match must be one of these existing names, or null if nothing is close:
{the names from foods.json, one per line}
- aliases are lowercase strings a person might actually type for that row.
- Return only the JSON array, no markdown fence, no prose.
```

## Why the rules stay out of the prompt

It is tempting to hand Claude the plate and ask for advice. Don't, for two
reasons. First, the advice becomes unauditable: you cannot diff it, you cannot
unit test it, and when it says something wrong you have nowhere to go. `rules.py`
is 225 lines you can read and argue with. Second, a model asked for nutrition
advice will happily produce "reduces absorption by up to 62%", and that number
is invented. A rules layer says "substantially" because that is what the
evidence actually supports, every single run.

Vision is the one job here a model does better than code: looking at a plate and
saying "lentils". Give it that job and nothing more.

## Tuning

- **It returns sentences**: add "Output must match this regex: `^[a-z ,]+$`."
- **It over-describes**: it returns "grilled chicken breast with lemon glaze".
  Add "Use one or two words per food. Do not describe preparation."
- **It misses the drink**: add "Include every drink in the frame, including water,
  tea and coffee." Beverages are where the inhibitor rules live.
- **It guesses foods that are not there**: add "Only name what you can actually
  see. If you are unsure, leave it out."
- **You want portions too**: add "Append an estimated weight in grams after each
  food, like `lentils 200g`." `lens.py` already parses that form.

## A note on privacy

Prompt 1 sends one thing: the bytes of the image you named on the command line.
Not your profile, not your concerns, not your supplement list, not `foods.json`,
not the advice. Prompt 2 sends food name strings only, no amounts and no photo.
Both are opt-in, and the default path sends nothing.
