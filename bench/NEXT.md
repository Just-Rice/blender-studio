# Where the benchmark stands (hand-off, 6 November 2026)

Development is paused after cycle 1. Results: `bench/RESULTS.md`; raw runs: `~/BlenderStudio/bench/cycle1`
and `cycle1-fix` (retest); decisions: `bench/history/`.

## Leads not yet fixed
- Hillside: no model's ground rises like a hillside. The hill-shape terrain did not help (reverted); try
  framing/camera guidance for landscapes instead, and clouds that do not look like plastic.
- Wood grain renders as wavy stripes on flat boards (judge noticed in the spill).
- Opus gains nothing from the tools (6.5 vs 6.6): look at its losses (mug framing, cheese bite, spill).
- "Checking a watch" pose does not read in the bus stop; the robot's wave is unclear in video.

## Running the next cycle (only when the user says go)
1. Check usage (a one-line `claude -p` with stream-json shows `rate_limit_event`).
2. `BENCH_USAGE_LIMIT=0.95 uv run python bench/cycle.py cycle2 --parallel --models claude-haiku-4-5-20251001,claude-haiku-5-5,claude-sonnet-5-5,claude-opus-5-5 --plain-from ~/BlenderStudio/bench/cycle1 --previous ~/BlenderStudio/bench/cycle1`
3. Alongside it: `zsh ~/BlenderStudio/guard.sh ~/BlenderStudio/bench/cycle2 0.95` (usage stop and memory guard)
   and `zsh ~/BlenderStudio/stats.sh` (machine stats). On a 16 GB Mac keep at most 2-4 Blenders running.
4. Build pages: `uv run python bench/pages/build.py RUNS ARTIFACT_OUT docs TEXT.json [FIX_DIR]`.
