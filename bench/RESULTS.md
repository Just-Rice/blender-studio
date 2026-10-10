# Benchmark: plain Blender versus Blender Studio

Run on 10 October 2026 on one Mac with Blender 5.2. The same model was given the same one-line request
twice: once with plain Blender (three tools: list the scene, run Python, render) and once with Blender
Studio's 43 tools. One attempt per pair.

## Summary

- A blind judge (Claude Opus 5.5, shown each pair twice in swapped order) preferred the Blender Studio
  picture in 6 of 7 pairs, with one tie. Average score rose from 3.5 to 5.1 out of 10.
- Claude Haiku 4.5 gained most: 1.5 to 4.0, while costing less ($0.39 against $0.54 over three requests).
- Claude Sonnet 5.5 barely needed the help: 5.5 to 6.7, at 2.4 times the cost and time. It read 8.7 times as
  many tokens, mostly because all 43 tool descriptions are sent with every request.
- Failed tool calls: 16 of 120 with plain Blender, 10 of 204 with Blender Studio.
- No picture from either way averaged above 7 out of 10.

## Every run

| Model | Task | Way | Judge /10 | Model time | Total time | Tokens written | Tokens read | Calls | Failed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Ceramic mug product shot | Plain Blender | 1.0 | 93 s | 208 s | 8k | 282k | 24 | 3 |
| Claude Haiku 4.5 | Ceramic mug product shot | Blender Studio | 3.0 | 53 s | 207 s | 4k | 271k | 20 | 0 |
| Claude Haiku 4.5 | Low-poly campsite at dusk | Plain Blender | 1.0 | 177 s | 1638 s | 14k | 841k | 40 | 4 |
| Claude Haiku 4.5 | Low-poly campsite at dusk | Blender Studio | 5.0 | 57 s | 139 s | 4k | 143k | 28 | 0 |
| Claude Haiku 4.5 | Toy robot waving | Plain Blender | 2.5 | 144 s | 179 s | 11k | 598k | 33 | 3 |
| Claude Haiku 4.5 | Toy robot waving | Blender Studio | 4.0 | 118 s | 256 s | 11k | 920k | 78 | 3 |
| Claude Sonnet 5.5 | Ceramic mug product shot | Plain Blender | 4.0 | 15 s | 22 s | 2k | 12k | 4 | 0 |
| Claude Sonnet 5.5 | Ceramic mug product shot | Blender Studio | 6.0 | 16 s | 84 s | 2k | 91k | 10 | 0 |
| Claude Sonnet 5.5 | Low-poly campsite at dusk | Plain Blender | 6.0 | 16 s | 30 s | 2k | 20k | 6 | 1 |
| Claude Sonnet 5.5 | Low-poly campsite at dusk | Blender Studio | 7.0 | 37 s | 68 s | 6k | 153k | 10 | 1 |
| Claude Sonnet 5.5 | Toy robot waving | Plain Blender | 6.5 | 19 s | 29 s | 3k | 13k | 4 | 0 |
| Claude Sonnet 5.5 | Toy robot waving | Blender Studio | 7.0 | 24 s | 44 s | 4k | 148k | 30 | 0 |
| Gemini 3.6 Flash | Ceramic mug product shot | Plain Blender | 3.5 | 223 s | 487 s | 34k | 180k | 9 | 5 |
| Gemini 3.6 Flash | Ceramic mug product shot | Blender Studio | 4.0 | 105 s | 116 s | 5k | 76k | 28 | 6 |

"Tokens read" counts everything sent to the model across all requests, including cached repeats.

## Limits

- One attempt per pair and three simple still-life requests; a repeat could move any single number a lot.
- The plain-Blender baseline is this repository's own minimal stand-in (`bench/baseline_server.py`), not
  another published package.
- One judge, and it is a Claude model scoring pictures mostly made by Claude models.
- Gemini has one pair: 3.5 Flash had no free allowance, 3.8 Flash kept timing out, and the free allowance cut
  the Blender Studio side of the 3.6 Flash pair off after 8 of its 9 turns.
- One plain-Blender run (Haiku, campsite) spent 27 minutes, nearly all rendering with settings it chose.
- The run exposed a defect, since fixed: `create_limbs` used a 10 cm default thickness, which buried
  Haiku's 10 cm mug under its own handle. The scores above are from before the fix.
- Run by the project's author, not independently.

## Run it yourself

```
uv run python bench/run.py out --claude claude-haiku-4-5-20251001,claude-sonnet-5-5 --tasks mug,camp,robot
GEMINI_API_KEY=... uv run python bench/run.py out --gemini gemini-3.6-flash:mug
cd bench && uv run python judge.py ../out
```

Claude runs need the Claude command line installed and signed in.
