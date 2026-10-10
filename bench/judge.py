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

from run import TASKS

QUESTION = """Two artists were given the same request: "{task}"

Their finished pictures are the files first.jpg and second.jpg in the current folder. Read both, then judge
them as an art director would. Score each from 1 (poor) to 10 (excellent) on:
- request: does it show what was asked for, recognisably?
- composition: framing, camera angle, use of the frame
- lighting: is it well lit, with shape and mood?
- materials: do surfaces and colours look considered?
- overall: would you accept this picture?

Reply with only a JSON object, no other text:
{{"first": {{"request": 0, "composition": 0, "lighting": 0, "materials": 0, "overall": 0}},
 "second": {{"request": 0, "composition": 0, "lighting": 0, "materials": 0, "overall": 0}},
 "better": "first" or "second" or "tie", "reason": "one sentence"}}"""


def ask(judge, task, first, second, folder):
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(first, folder / "first.jpg")
    shutil.copy(second, folder / "second.jpg")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    command = ["claude", "-p", QUESTION.format(task=TASKS[task]), "--model", judge, "--tools", "Read",
               "--allowedTools", "Read", "--strict-mcp-config", "--disable-slash-commands", "--setting-sources",
               "project", "--system-prompt", "You are an experienced art director judging 3D renders.",
               "--output-format", "json", "--max-turns", "6", "--no-session-persistence"]
    done = subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True, timeout=300)
    reply = json.loads(done.stdout[done.stdout.find("{"):done.stdout.rfind("}") + 1]).get("result", "")
    match = re.search(r"\{.*\}", reply, re.S)
    return json.loads(match.group(0)) if match else {"error": reply[:300]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--judge", default="claude-opus-5-5")
    args = parser.parse_args()
    runs = [json.loads(p.read_text()) | {"dir": p.parent} for p in sorted(args.out.glob("*/metrics.json"))]
    pairs = {}
    for run in runs:
        pairs.setdefault((run["model"], run["task"]), {})[run["arm"]] = run
    results_path = args.out / "judging.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    rng = random.Random(7)
    for (model, task), arms in sorted(pairs.items()):
        key = f"{model}__{task}"
        if key in results or len(arms) < 2:
            continue
        finals = {arm: run["dir"] / run["shots"][-1] for arm, run in arms.items() if run.get("shots")}
        if len(finals) < 2:
            missing = [arm for arm in arms if arm not in finals]
            results[key] = {"model": model, "task": task, "no_picture": missing,
                            "winner": next(iter(finals), None)}
            continue
        verdicts = []
        order = ["plain", "studio"]
        rng.shuffle(order)
        for position, (a, b) in enumerate((order, order[::-1])):
            verdict = ask(args.judge, task, finals[a], finals[b], args.out / "judging" / f"{key}__{position}")
            verdict["first_was"], verdict["second_was"] = a, b
            verdicts.append(verdict)
            print(key, f"first={a}", verdict.get("better"), verdict.get("reason", verdict.get("error"))[:140],
                  flush=True)
        scores = {arm: {} for arm in ("plain", "studio")}
        wins = {"plain": 0, "studio": 0, "tie": 0}
        for verdict in verdicts:
            if "error" in verdict:
                continue
            for slot in ("first", "second"):
                for criterion, value in verdict[slot].items():
                    scores[verdict[f"{slot}_was"]].setdefault(criterion, []).append(value)
            better = verdict.get("better")
            wins[verdict[f"{better}_was"] if better in ("first", "second") else "tie"] += 1
        averaged = {arm: {c: sum(v) / len(v) for c, v in crit.items()} for arm, crit in scores.items()}
        winner = "studio" if wins["studio"] > wins["plain"] else "plain" if wins["plain"] > wins["studio"] else "tie"
        results[key] = {"model": model, "task": task, "judge": args.judge, "scores": averaged, "wins": wins,
                        "winner": winner, "verdicts": verdicts}
        results_path.write_text(json.dumps(results, indent=1))
    results_path.write_text(json.dumps(results, indent=1))
    print("judged", len(results), "pairs")


if __name__ == "__main__":
    main()
