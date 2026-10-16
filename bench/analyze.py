"""Turn one cycle's runs and judging into a findings report: where scores are lost, and why.

    uv run python bench/analyze.py CYCLE_DIR

Writes CYCLE_DIR/findings.md and CYCLE_DIR/summary.json.
"""
import asyncio
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tasks import TASKS  # noqa: E402

CRITERIA = ("request", "composition", "lighting", "materials", "overall")


def all_tool_names():
    from blender_studio import server
    return sorted(tool.name for tool in asyncio.run(server.mcp.list_tools()))


def main():
    cycle = Path(sys.argv[1])
    runs = {(r["model"], r["task"], r["arm"]): r for p in sorted(cycle.glob("*/metrics.json"))
            for r in [json.loads(p.read_text())]}
    judging = json.loads((cycle / "judging.json").read_text()) if (cycle / "judging.json").exists() else {}
    versus = json.loads((cycle / "versus.json").read_text()) if (cycle / "versus.json").exists() else {}
    lines = [f"# Findings for {cycle.name}", ""]

    # Overall
    pairs = [j for j in judging.values() if j.get("scores")]
    mean = lambda arm, c="overall": statistics.mean(j["scores"][arm][c] for j in pairs) if pairs else None
    ticked = lambda arm: [j["checklist"][arm] for j in pairs if j.get("checklist", {}).get(arm) is not None]
    wins = Counter(j.get("winner") for j in pairs)
    summary = {"pairs": len(pairs), "wins": dict(wins),
               "mean": {a: mean(a) for a in ("plain", "studio")},
               "checklist": {a: (statistics.mean(ticked(a)) if ticked(a) else None) for a in ("plain", "studio")},
               "by_model": {}, "by_task": {}, "versus": {}}
    if pairs:
        lines += ["## Overall", "",
                  f"- Pairs judged: {len(pairs)}. Blender Studio better in {wins['studio']}, plain in {wins['plain']}, "
                  f"ties {wins['tie']}.",
                  f"- Average overall score: plain {mean('plain'):.2f}, studio {mean('studio'):.2f}.",
                  "- Checklist met: " + ", ".join(
                      f"{a} {summary['checklist'][a]:.0%}" if summary['checklist'][a] is not None else f"{a} n/a"
                      for a in ("plain", "studio")) + ".", ""]
    if versus:
        changed = [v for v in versus.values() if v.get("scores")]
        vw = Counter(v["winner"] for v in changed)
        summary["versus"] = {"pairs": len(changed), "after_better": vw["after"], "before_better": vw["before"],
                             "ties": vw["tie"]}
        lines += ["## Against the previous cycle (Blender Studio pictures only)", "",
                  f"- This cycle's picture judged better in {vw['after']} of {len(changed)}, the previous cycle's in "
                  f"{vw['before']}, ties {vw['tie']}.", ""]

    # By model and by task
    for key, label in (("model", "By model"), ("task", "By request")):
        groups = defaultdict(list)
        for j in pairs:
            groups[j[key]].append(j)
        lines += [f"## {label}", "", "| | Plain | Studio | Studio wins | Checklist plain | Checklist studio |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for name, items in sorted(groups.items()):
            p = statistics.mean(j["scores"]["plain"]["overall"] for j in items)
            s = statistics.mean(j["scores"]["studio"]["overall"] for j in items)
            cp = [j["checklist"]["plain"] for j in items if j.get("checklist", {}).get("plain") is not None]
            cs = [j["checklist"]["studio"] for j in items if j.get("checklist", {}).get("studio") is not None]
            won = sum(j["winner"] == "studio" for j in items)
            summary["by_" + key][name] = {"plain": p, "studio": s, "studio_wins": won, "pairs": len(items),
                                          "checklist_plain": statistics.mean(cp) if cp else None,
                                          "checklist_studio": statistics.mean(cs) if cs else None}
            fmt = lambda v: f"{v:.0%}" if v is not None else "n/a"
            lines.append(f"| {name} | {p:.1f} | {s:.1f} | {won} of {len(items)} | "
                         f"{fmt(summary['by_' + key][name]['checklist_plain'])} | "
                         f"{fmt(summary['by_' + key][name]['checklist_studio'])} |")
        lines.append("")

    # Weakest criteria with the tools
    if pairs:
        lines += ["## Weakest criteria with Blender Studio (average across all pairs)", ""]
        for c in sorted(CRITERIA, key=lambda c: mean("studio", c)):
            lines.append(f"- {c}: studio {mean('studio', c):.2f}, plain {mean('plain', c):.2f}")
        lines.append("")

    # Losses and misses, with the judge's words
    lines += ["## Pairs plain Blender won, and checklist items the tools missed", ""]
    for key, j in sorted(judging.items()):
        if not j.get("scores"):
            lines.append(f"- **{key}**: no picture from {', '.join(j.get('no_picture', []))}")
            continue
        missed = []
        items = TASKS.get(j["task"], {}).get("checklist", [])
        for v in j.get("verdicts", []):
            slot = "first" if v.get("first_was") == "studio" else "second"
            for item, ok in zip(items, v.get("checklist", {}).get(slot, [])):
                if not ok and item not in missed:
                    missed.append(item)
        if j["winner"] == "plain" or missed:
            reason = next((v.get("reason") for v in j.get("verdicts", []) if v.get("reason")), "")
            lines.append(f"- **{key}** ({j['winner']} won, studio {j['scores']['studio']['overall']:.1f} vs plain "
                         f"{j['scores']['plain']['overall']:.1f}). Missed: {'; '.join(missed) or 'nothing'}. "
                         f"Judge: {reason}")
    lines.append("")

    # Tool use
    studio = [r for (m, t, a), r in runs.items() if a == "studio"]
    used = Counter()
    for r in studio:
        used.update(r.get("tools_used", {}))
    total_calls = sum(used.values()) or 1
    names = all_tool_names()
    never = [n for n in names if n not in used]
    lines += ["## How the tools were used", "",
              f"- Tool calls with Blender Studio: {total_calls}. Own code (run_python): "
              f"{used.get('run_python', 0)} ({used.get('run_python', 0) / total_calls:.0%}).",
              f"- Never used this cycle ({len(never)} of {len(names)}): {', '.join(never)}.",
              "- Most used: " + ", ".join(f"{n} {c}" for n, c in used.most_common(12)) + ".", ""]
    summary["tools_used"] = dict(used)
    summary["tools_never_used"] = never

    # Failures and unfinished runs
    lines += ["## Failed calls and unfinished runs", ""]
    errors = Counter()
    for (m, t, a), r in sorted(runs.items()):
        for e in r.get("errors", []):
            errors[(a, e.get("tool"), e.get("error", "")[:160].split("Traceback")[0].strip())] += 1
        if not r.get("finished"):
            lines.append(f"- Unfinished: {m} {t} {a}: {r.get('stop') or r.get('crashed')}")
    for (a, tool, text), n in errors.most_common(25):
        lines.append(f"- {a} {tool} x{n}: {text}")
    lines.append("")

    # Cost
    lines += ["## Cost and effort (totals)", "", "| Model | Way | Cost | Tokens read | Tokens written | Model time | Total time |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    totals = defaultdict(lambda: defaultdict(float))
    for (m, t, a), r in runs.items():
        for f in ("cost_usd", "input_tokens", "output_tokens", "api_s", "wall_s"):
            totals[(m, a)][f] += r.get(f) or 0
    for (m, a), t in sorted(totals.items()):
        lines.append(f"| {m} | {a} | ${t['cost_usd']:.2f} | {t['input_tokens'] / 1000:.0f}k | "
                     f"{t['output_tokens'] / 1000:.0f}k | {t['api_s']:.0f} s | {t['wall_s']:.0f} s |")
    summary["cost"] = {f"{m} {a}": dict(t) for (m, a), t in totals.items()}

    (cycle / "findings.md").write_text("\n".join(lines) + "\n")
    (cycle / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
