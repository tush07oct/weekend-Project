# Prompts: Content Brain

The local path uses no prompts. Images go through the tesseract CLI, and filing
is term overlap against `projects.md`. These two prompts are the optional `--ai`
layer: one reads an image when tesseract is not available, one breaks the ties
the local scorer flagged as too close to call.

## Prompt 1: Read the image

This is the vision prompt in `content_brain.py`. It ships as an image block plus
this text, and nothing else.

```
Transcribe every word of text in this image. Output the text only, no commentary.
```

Short on purpose. Anything you add here ("summarize", "what is this about")
invites the model to interpret instead of transcribe, and then your scorer is
matching against a paraphrase instead of against what the screenshot said.

## Prompt 2: Place the close calls

This is the one wired into `--ai` in `build_board.py`. It only ever sees the items
whose top two project scores were within 1.0 of each other.

```
My projects:
{one project name per line, with a leading dash}

Each item below is something I saved. Say which single project it serves, or
'unfiled' if none of them do.
Return one line per item, exactly 'index: project name', nothing else.

[0] {filename}
{item text, first 400 characters}

[1] {filename}
{item text, first 400 characters}
```

## Why only the close calls get sent matters

An item that scored 7 on one project and 0 on the rest does not need a model, and
sending it costs you money, latency and privacy for no change in the answer. The
local scorer already knows when it is guessing: that is what the gap between the
top two scores tells you. So the model is a tie-breaker, not a classifier. On the
sample data that means most runs send nothing at all, and the `--ai` flag becomes
something you can leave on without thinking about it.

The other half of this is that the project names come from `projects.md`. The
model is told to pick one of your names or say `unfiled`, and anything it returns
that is not an exact name match is thrown away. A classifier that can invent a
category will invent one, and then your board grows a section you never asked for.

## Tuning

- **It invents a project name**: add "Use the project names exactly as written
  above. Do not shorten them or invent new ones."
- **It refuses to say unfiled**: add "Most items do not belong to any project.
  'unfiled' is the right answer more often than not."
- **The output is prose instead of lines**: add "No preamble, no explanation, no
  markdown. One line per item or the output is unusable."
- **Transcription comes back summarized**: add "Include every word, including
  usernames, timestamps and button labels. Do not describe the image."
- **Handwriting or a photographed screen**: tesseract will fail here and the
  vision read is genuinely better. Add "Some text may be handwritten; transcribe
  it anyway and do not guess at words you cannot read, write [?] instead."

## A note on privacy

Prompt 1 uploads one image file, base64-encoded, exactly as it sits on disk. Not
the filename, not the folder listing, not your `projects.md`, not any other
image. One call per image, and only for images tesseract could not read.

Prompt 2 uploads your project names and the text of the close-call items only.
Items the local scorer placed confidently never leave the machine, and neither
does the raw image for any of them.

Neither prompt runs without `--ai` and `ANTHROPIC_API_KEY`. `ask.py` has no
model path at all, so searching your pile is always local.
