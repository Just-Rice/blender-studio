"""Blind judging for the benchmark: a model that did not take part compares each pair of final pictures.

    uv run python bench/judge.py OUT [--judge claude-opus-5-5]

For every model and task, the plain-Blender picture and the Blender Studio picture are copied to
neutral file names in a random order and shown to the judge twice, once each way round, so neither
side benefits from being seen first. Writes OUT/judging.json.
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
from pathlib import Path

from tasks import TASKS

QUESTION = """Two artists were given the same request: "{task}"

Their finished pictures are the files first.jpg and second.jpg in the current folder. Read both. A picture made
of several frames side by side is a strip from a short video: judge the motion across its frames as well.

First tick this checklist for each picture, true or false, in this order:
{checklist}

Then judge them as an art director would. Score each from 1 (poor) to 10 (excellent) on:
- request: does it show what was asked for, recognisably?
- composition: framing, camera angle, use of the frame
- lighting: is it well lit, with shape and mood?
- materials: do surfaces and colours look considered?
- overall: would you accept this picture?

Reply with only a JSON object, no other text:
{{"checklist": {{"first": [true, false, ...], "second": [true, false, ...]}},
 "first": {{"request": 0, "composition": 0, "lighting": 0, "materials": 0, "overall": 0}},
 "second": {{"request": 0, "composition": 0, "lighting": 0, "materials": 0, "overall": 0}},
 "better": "first" or "second" or "tie", "reason": "one sentence"}}"""


def ask(judge, task, first, second, folder):
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(first, folder / "first.jpg")
    shutil.copy(second, folder / "second.jpg")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    items = "\n".join(f"{n}. {item}" for n, item in enumerate(TASKS[task]["checklist"], 1))
    question = QUESTION.format(task=TASKS[task]["brief"], checklist=items)
    command = ["claude", "-p", question, "--model", judge, "--tools", "Read",
               "--allowedTools", "Read", "--strict-mcp-config", "--disable-slash-commands", "--setting-sources",
               "project", "--system-prompt", "You are an experienced art director judging 3D renders.",
               "--output-format", "json", "--max-turns", "6", "--no-session-persistence"]
    done = subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True, timeout=300)
    reply = json.loads(done.stdout[done.stdout.find("{"):done.stdout.rfind("}") + 1]).get("result", "")
    match = re.search(r"\{.*\}", reply, re.S)
    return json.loads(match.group(0)) if match else {"error": reply[:300]}


def judge_pair(judge, task, pictures, folder, rng):
    """pictures: {label: path} for exactly two labels. Shown twice, once each way round."""
    order = list(pictures)
    rng.shuffle(order)
    verdicts = []
    for position, (a, b) in enumerate((order, order[::-1])):
        verdict = ask(judge, task, pictures[a], pictures[b], folder / str(position))
        verdict["first_was"], verdict["second_was"] = a, b
        verdicts.append(verdict)
        print(folder.name, f"first={a}", verdict.get("better"), str(verdict.get("reason", verdict.get("error")))[:140],
              flush=True)
    scores = {label: {} for label in pictures}
    ticks = {label: [] for label in pictures}
    wins = {**{label: 0 for label in pictures}, "tie": 0}
    for verdict in verdicts:
        if "error" in verdict:
            continue
        for slot in ("first", "second"):
            label = verdict[f"{slot}_was"]
            for criterion, value in verdict[slot].items():
                scores[label].setdefault(criterion, []).append(value)
            ticks[label] += [bool(x) for x in verdict.get("checklist", {}).get(slot, [])]
        better = verdict.get("better")
        wins[verdict[f"{better}_was"] if better in ("first", "second") else "tie"] += 1
    averaged = {label: {c: sum(v) / len(v) for c, v in crit.items()} for label, crit in scores.items()}
    checklist = {label: (sum(t) / len(t) if t else None) for label, t in ticks.items()}
    a, b = list(pictures)
    winner = a if wins[a] > wins[b] else b if wins[b] > wins[a] else "tie"
    return {"task": task, "judge": judge, "scores": averaged, "checklist": checklist, "wins": wins,
            "winner": winner, "verdicts": verdicts}


def final_picture(run):
    return run["dir"] / run["shots"][-1] if run.get("shots") else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--judge", default="claude-opus-5-5")
    parser.add_argument("--versus", type=Path, default=None,
                        help="an earlier cycle: compare its Blender Studio pictures with this cycle's instead")
    args = parser.parse_args()
    load = lambda folder: {(r["model"], r["task"], r["arm"]): r | {"dir": p.parent}
                           for p in sorted(folder.glob("*/metrics.json")) for r in [json.loads(p.read_text())]}
    runs = load(args.out)
    if args.versus:
        earlier = load(args.versus)
        jobs = {(m, t): {"before": earlier[(m, t, "studio")], "after": run} for (m, t, arm), run in runs.items()
                if arm == "studio" and (m, t, "studio") in earlier}
        results_path, folder_name = args.out / "versus.json", "versus"
    else:
        jobs = {(m, t): {"plain": runs[(m, t, "plain")], "studio": run} for (m, t, arm), run in runs.items()
                if arm == "studio" and (m, t, "plain") in runs}
        results_path, folder_name = args.out / "judging.json", "judging"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    rng = random.Random(7)
    for (model, task), sides in sorted(jobs.items()):
        key = f"{model}__{task}"
        if key in results:
            continue
        pictures = {label: final_picture(run) for label, run in sides.items()}
        missing = [label for label, path in pictures.items() if path is None]
        if missing:
            results[key] = {"model": model, "task": task, "no_picture": missing,
                            "winner": next((l for l in pictures if l not in missing), None)}
        else:
            results[key] = {"model": model, **judge_pair(args.judge, task, pictures,
                                                          args.out / folder_name / key, rng)}
        results_path.write_text(json.dumps(results, indent=1))
    results_path.write_text(json.dumps(results, indent=1))
    print("judged", len(results), "pairs")


if __name__ == "__main__":
    main()
