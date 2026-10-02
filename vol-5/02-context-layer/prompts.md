# Prompts: Context Layer

The local path uses no prompts at all. `init.py` asks the questions, you answer,
`context.py` concatenates files. These two prompts are for the people who would
rather be interviewed by a model than by a Python input loop, and for anyone who
wants to see the exact shape of the block the loader produces.

## Prompt 1: Conduct the interview

Paste this into any assistant, then answer out loud until it stops asking. At the
end it hands you markdown you drop straight into `rooms/` and `profile.md`.

```
You are interviewing me to build a personal context file about one area of my
life. The area is: {work | content | family | money}

Your goal is a short markdown file another assistant could read in 20 seconds and
then help me as if it had known me for a year.

How to run the interview:
- Ask ONE question at a time. Wait for my answer. Never batch questions.
- Start with these headings, in order: {paste the headings from rooms/{room}.md}
- Ask at most 3 questions per heading, fewer if my answer is already specific.
- When an answer is vague, ask one follow-up that forces a specific: a name, a
  number, a date, a real example. "I'm busy" is not an answer; "I stop at 15:45
  for school pickup" is.
- Ask about the things people forget to say out loud: who decides, what cannot
  change, which words mean something specific here, what I do NOT want help with.
- Do not suggest answers. Do not fill gaps with what a typical person would say.
- Stop after the last heading. Do not ask if I want to add anything.

Then output ONLY the finished file, in this format:

# {Title}
## {Heading}
- one fact per line, under 15 words, no sentences that would be true of anyone
...

Rules for the output:
- Keep my words. Compress, do not rewrite into neutral professional English.
- Numbers wherever I gave one. Names wherever I gave one.
- No preamble, no closing commentary, no "feel free to edit".
- If a heading has nothing real under it, write _(not filled yet)_ and move on.
```

## Prompt 2: The context-assembly template

This is exactly what `context.py {room}` prints. Copy it if you want to assemble
blocks by hand, or to port the idea to another language.

```
# Context for {room}

## Who I am

{contents of profile.md, H1 stripped, headings pushed down one level}

## How to work with me

{contents of rules.md, H1 stripped, headings pushed down one level}

## Room: {room}

{contents of rooms/{room}.md, H1 stripped, headings pushed down one level}

## Recent corrections

- {YYYY-MM-DD}: {correction}
- {YYYY-MM-DD}: {correction}
{the last N entries from memory.md, untagged ones plus ones tagged [{room}]}

## How to use this

Treat the above as background, not as a task. Follow the rules and the
corrections even when I forget to restate them. Ask before assuming anything the
files do not say.
```

## Why the room, not everything, matters

The obvious version of this project is one big `about-me.md`. It fails in two
ways. It gets long, so the parts that matter to the current task compete with the
parts that do not, and models follow the start and end of a long block far better
than the middle. And it leaks: your salary and your kids' school do not belong in
a chat about a design review. Picking the room is one word on the command line
and it solves both. The corrections log stays global by default because a
preference like "metric only" is not a work preference.

The second design choice worth copying: corrections are dated and append-only.
You can see that a rule has been in force since January, and you never lose the
earlier version of a preference by editing it away. Order carries information,
newest last, so the most recent correction is the last thing the model reads.

## Tuning

- **The interview gets vague answers**: add "After any answer under 10 words, ask
  one follow-up before moving on."
- **The model writes your file in corporate English**: add "Use my exact nouns and
  verbs. If I said 'the board', do not write 'the dispatch interface'."
- **The output is padded**: add "Maximum 6 bullets per heading. Delete the weakest
  rather than adding a seventh."
- **It invents facts you never said**: add "Every line must trace to something I
  said in this conversation. Write nothing I did not say."
- **The assembled block gets ignored in the chat**: move the rules section last.
  Some models weight the final section most, and rules are what you want obeyed.
- **The block is too long for a model you use**: lower `--memory`, and split the
  room. A block over 800 words is a sign the room file is doing two jobs.

## A note on privacy

Neither prompt is sent anywhere by this project. `init.py`, `memory.py`, and
`context.py` make no network calls and need no API key; the only outbound path in
the whole folder is `pbcopy`, which writes to your own clipboard.

If you use Prompt 1, you are telling an assistant about one area of your life in
a chat window, which is the same exposure as any other conversation, and it is
your choice per room. The safer order is to run `init.py` locally first and use
the prompt only for the rooms you do not mind discussing. If you use Prompt 2 by
pasting an assembled block, read it before you paste it: it is one room plus your
profile and rules, deliberately not everything.
