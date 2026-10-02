# Vol 5: 5 Builds You'll Actually Use (October 2026)

5 projects that earn their place on your machine. Not demos you run once and
delete: a board that files everything you save, the context file every assistant
should have asked you for, a plate of food turned into something to do, a brand
animation you can render, and an agent that teaches itself a game while you
watch. Each one teaches a different core concept you'll reuse for years.

| # | Project | Difficulty | Time | What you get |
|---|---------|---|---|---|
| 01 | [Content Brain](01-content-brain) | Medium | 4-6h | A folder of screenshots and notes becomes a board, filed under your own projects |
| 02 | [Context Layer](02-context-layer) | Easy-Medium | 3-5h | The onboarding every AI should have gotten about you, in files you own |
| 03 | [Nutrition Lens](03-nutrition-lens) | Medium | 4-6h | A plate of food becomes pairings, timing, and what blocks what |
| 04 | [Motion Studio](04-motion-studio) | Medium-Advanced | 5-8h | Three lines of brief becomes a branded animation, critiqued and rendered |
| 05 | [The Arena](05-the-arena) | Advanced | Full day | A tiny game, and an agent that goes from random to unbeatable while you watch |

## Each project teaches a different concept

- **Vision and OCR (#1)**: getting text out of images locally, then classifying
  the result against categories that are yours, not a model's defaults.
- **Context and memory (#2)**: the difference between a model that knows your
  situation and one you re-explain yourself to every morning, built as plain
  files you own rather than a vendor's memory feature.
- **Vision, structured data, and rules (#3)**: the pattern behind most useful
  AI products. A model identifies, a database grounds, and a rules layer turns
  facts into an action. The model is one third of the system.
- **Directing a model (#4)**: critique and iteration as a real loop, plus the
  render pipeline that turns a browser animation into a file you can post.
- **Reinforcement learning (#5)**: states, actions, rewards, and trial and
  error, written as a Q-table in plain Python so you can read every line of it.

Build all 5 and you've covered OCR, context engineering, grounded rules, model
direction, and reinforcement learning: five patterns that show up everywhere.

## Local vs API, at a glance

Every project runs its core **fully locally**. Two of them (**#2 Context Layer**
and **#5 The Arena**) make no network calls at all, with no key, not even
optionally. The other three take an **optional** Anthropic API key for one
specific layer: reading an image when tesseract isn't installed (#1),
identifying food from a photo (#3), and writing a fresher animation or a sharper
critique (#4). Each of those has a local fallback that is the default path, so
nothing breaks without a key. Each project's README states exactly which bytes
leave the machine when you do turn a key on.

## Pick one

If you save things constantly and never find them again: start with **#1 Content
Brain**. Point it at your screenshots folder and watch a board assemble itself.

If you're tired of explaining yourself to a fresh chat: **#2 Context Layer**.
One evening of answering questions, then paste one block and be known.

If you want the most useful thing here per hour spent: **#3 Nutrition Lens**.
Type what you ate and get a change you can make at the next meal.

If you make things people watch: **#4 Motion Studio**. Set your brand once, then
go from three lines to a rendered animation in an evening.

If you want to understand the idea behind the famous results: **#5 The Arena**.
Watch an agent fail a thousand times and then stop failing.

## Want an earlier volume?

[Go back to the root](../README.md), where vol 4 through vol 1 are linked.
