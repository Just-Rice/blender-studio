"""One measurement cycle: run, judge (against plain and against the previous cycle), analyse, record.

    uv run python bench/cycle.py NAME --models claude-haiku-5-5,claude-opus-5-5 [--tasks regular|holdout|all|a,b]
                                      [--plain-from DIR,DIR] [--previous DIR] [--gemini model:task]

Raw runs go to ~/BlenderStudio/bench/NAME. The summary is copied to bench/history/NAME.json. Re-running the same
command resumes: finished runs and judged pairs are skipped.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tasks import HOLDOUT, REGULAR  # noqa: E402

RUNS = Path.home() / "BlenderStudio" / "bench"


def step(*command):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    print("\n$", " ".join(str(c) for c in command), flush=True)
    return subprocess.run([sys.executable, *map(str, command)], cwd=HERE, env=env).returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--models", required=True)
    parser.add_argument("--tasks", default="regular")
    parser.add_argument("--plain-from", default="")
    parser.add_argument("--previous", default="")
    parser.add_argument("--gemini", default="")
    parser.add_argument("--judge", default="claude-opus-5-5")
    args = parser.parse_args()
    tasks = {"regular": REGULAR, "holdout": HOLDOUT, "all": REGULAR + HOLDOUT}.get(args.tasks, args.tasks.split(","))
    out = RUNS / args.name
    out.mkdir(parents=True, exist_ok=True)
    run_args = ["run.py", out, "--claude", args.models, "--tasks", ",".join(tasks)]
    if args.plain_from:
        run_args += ["--plain-from", args.plain_from]
    if args.gemini:
        run_args += ["--gemini", args.gemini]
    code = step(*run_args)
    if code == 3:
        print("Stopped for the usage limit. Run the same command again later to carry on.")
        return code
    step("judge.py", out, "--judge", args.judge)
    if args.previous:
        step("judge.py", out, "--judge", args.judge, "--versus", args.previous)
    step("analyze.py", out)
    history = HERE / "history"
    history.mkdir(exist_ok=True)
    summary = json.loads((out / "summary.json").read_text())
    summary["cycle"] = args.name
    summary["commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True,
                                       text=True).stdout.strip()
    (history / f"{args.name}.json").write_text(json.dumps(summary, indent=1, default=str))
    shutil.copy(out / "findings.md", history / f"{args.name}-findings.md")
    print(f"\nFindings: {out / 'findings.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
