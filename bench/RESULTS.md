# Benchmark: plain Blender versus Blender Studio

## Update, 13 October 2026: fixes after the Opus result, and an Opus re-run

Opus 5.5 scored lower with the tools (6.8) than without (7.7). Reading its recorded runs and the judge's
comments pointed to: framing measured from bounding boxes (small subject, dead space); ceramic and glossy
presets that were too mirror-like; a backdrop lit as brightly as the subject; a design guide that pushed
few shapes, few materials and muted colours; false "duplicate" alarms from the scene check; and materials
that had to be set one call at a time. All were changed, and tool descriptions were cut by 27%.

Opus was then run again with the fixed tools on the same three requests and judged against its original
plain-Blender pictures:

| Task | Plain (first / second judging) | Tools before | Tools after |
| --- | --- | --- | --- |
| Ceramic mug product shot | 7.5 / 7.0 | 6.0 | 8.0 |
| Low-poly campsite at dusk | 7.5 / 7.0 | 7.5 | 9.0 |
| Toy robot waving | 8.0 / 7.5 | 7.0 | 8.0 |
| Average | 7.7 / 7.2 | 6.8 | 8.3 |

- Judged better with the tools in 3 of 3 pairs. Tokens read fell from 583k to 291k (plain: 152k); cost
  $1.00 against $1.11 before (plain: $0.94).
- One attempt per request. The same plain pictures scored 0.5 lower on the second judging, which is the
  size of the noise. On the campsite the re-run used no staging tools at all, only `run_python`.
- Other models have not been re-run with the fixed tools; the tables below show them with the tools as
  they were. `bench/replay.py` replays a recorded run against the current tools for free.

**All 13 pairs together** (Haiku 4.5, Haiku 5.5, Sonnet 5.5, Opus 5.5, Gemini 3.6 Flash): Blender Studio
judged better in 8, plain Blender in 3, 2 ties; average 5.6 against 4.9 out of 10. Without Haiku 4.5 the
other ten pairs average 6.0 against 5.9.

## Update, 13 October 2026: Claude Opus 5.5 added

With Haiku 5.5, Sonnet 5.5, Opus 5.5 and Gemini 3.6 Flash together (10 pairs), this is the current headline:

- The blind judge preferred the Blender Studio picture in 5 of 10 pairs and the plain one in 3, with 2 ties.
  Average score: 5.9 plain, 6.0 Blender Studio. Effectively a draw on quality.
- Opus 5.5 was better without the tools: 7.7 plain against 6.8. It won the mug and robot plain and tied on
  the campsite. It read 3.8 times as many tokens with the tools and cost $1.11 against $0.94, but its
  plain runs were slower (1,314 s against 512 s) because it chose heavy render settings.
- The pattern across models: the stronger the model, the less the tools help.
- The judge (Opus 5.5) also made the Opus pictures. It judged them blind like the rest.

| Model | Task | Way | Judge /10 | Model time | Total time | Tokens written | Tokens read | Calls | Failed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Opus 5.5 | Ceramic mug product shot | Plain Blender | 7.5 | 97 s | 798 s | 10k | 47k | 6 | 0 |
| Claude Opus 5.5 | Ceramic mug product shot | Blender Studio | 6.0 | 46 s | 137 s | 5k | 110k | 15 | 0 |
| Claude Opus 5.5 | Low-poly campsite at dusk | Plain Blender | 7.5 | 68 s | 83 s | 7k | 39k | 7 | 0 |
| Claude Opus 5.5 | Low-poly campsite at dusk | Blender Studio | 7.5 | 80 s | 124 s | 9k | 178k | 14 | 1 |
| Claude Opus 5.5 | Toy robot waving | Plain Blender | 8.0 | 94 s | 434 s | 10k | 67k | 9 | 1 |
| Claude Opus 5.5 | Toy robot waving | Blender Studio | 7.0 | 78 s | 251 s | 8k | 295k | 29 | 0 |

## Update, 13 October 2026: Claude Haiku 5.5

Claude Haiku 5.5 was run on the same three requests, and replaces Haiku 4.5 in the headline comparison.
With Haiku 5.5, Sonnet 5.5 and Gemini 3.6 Flash together:

- The blind judge preferred the Blender Studio picture in 5 of 7 pairs and the plain one in 1, with 1 tie.
  Average score rose from 5.2 to 5.7 out of 10.
- Haiku 5.5 did about as well on its own: 5.5 with plain Blender, 5.3 with the tools. The tools won on the
  mug and campsite; plain Blender won on the robot, 6.5 against 4.0.
- Haiku 5.5 read 4.7 times as many tokens with the tools (972k against 208k), wrote 28% fewer, took 411 s
  against 272 s in total, and cost $0.04 against $0.03. No tool call failed either way (0 of 21, 0 of 74).
- The larger gain seen with Haiku 4.5 below suggests the tools matter most for weaker models.

| Model | Task | Way | Judge /10 | Model time | Total time | Tokens written | Tokens read | Calls | Failed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 5.5 | Ceramic mug product shot | Plain Blender | 4.0 | 43 s | 128 s | 8k | 68k | 8 | 0 |
| Claude Haiku 5.5 | Ceramic mug product shot | Blender Studio | 5.0 | 98 s | 177 s | 12k | 467k | 27 | 0 |
| Claude Haiku 5.5 | Low-poly campsite at dusk | Plain Blender | 6.0 | 59 s | 70 s | 13k | 37k | 5 | 0 |
| Claude Haiku 5.5 | Low-poly campsite at dusk | Blender Studio | 7.0 | 32 s | 87 s | 6k | 265k | 26 | 0 |
| Claude Haiku 5.5 | Toy robot waving | Plain Blender | 6.5 | 55 s | 74 s | 11k | 102k | 8 | 0 |
| Claude Haiku 5.5 | Toy robot waving | Blender Studio | 4.0 | 25 s | 147 s | 4k | 241k | 21 | 0 |

These runs came after the `create_limbs` fix described below; the Sonnet and Gemini runs did not.

## Original run, 10 October 2026

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
