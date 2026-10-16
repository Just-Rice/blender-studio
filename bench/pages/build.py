"""Build the comparison for the project site and the benchmark artifact from raw benchmark runs.

    uv run python bench/pages/build.py RUNS_DIR ARTIFACT_OUT docs [bench/pages/text_v2.json]

Without text.json it only prints the facts, so the written summary can be based on them.
"""
import html
import json
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
runs_dir, out_artifact, site_docs = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
NAME = {"claude-haiku-4-5-20251001": "Claude Haiku 4.5", "claude-haiku-5-5": "Claude Haiku 5.5",
        "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-opus-5-5": "Claude Opus 5.5",
        "gemini-3.8-flash": "Gemini 3.8 Flash"}
TASKS = {"mug": "Ceramic mug product shot", "camp": "Low-poly campsite at dusk", "robot": "Toy robot waving"}
ARM = {"plain": "Plain Blender", "studio": "Blender Studio"}
# Judge averages from the first round, with the tools as they were: (plain, tools)
BEFORE = {"claude-haiku-4-5-20251001": (1.5, 4.0), "claude-haiku-5-5": (5.5, 5.3), "claude-sonnet-5-5": (5.5, 6.7),
          "claude-opus-5-5": (7.7, 6.8)}

runs = {}
for path in sorted(runs_dir.glob("*/metrics.json")):
    m = json.loads(path.read_text())
    runs[(m["model"], m["task"], m["arm"])] = m | {"dir": path.parent}
judging = json.loads((runs_dir / "judging.json").read_text())


def jd(model, task):
    return judging.get(f"{model}__{task}", {})


def score(model, task, arm):
    return jd(model, task).get("scores", {}).get(arm, {}).get("overall")


def k(value):
    return f"{value / 1000:.0f}k"


ALL = [(m, t) for m in NAME for t in TASKS if (m, t, "plain") in runs and (m, t, "studio") in runs
       and (runs[(m, t, "plain")].get("shots") or runs[(m, t, "studio")].get("shots"))]
PAIRS = [p for p in ALL if score(*p, "plain") is not None and score(*p, "studio") is not None]
UNSCORED = [p for p in ALL if p not in PAIRS]
MODELS = [m for m in NAME if any(p[0] == m for p in ALL)]
winner = {p: jd(*p).get("winner", "tie") for p in PAIRS}
wins = {w: sum(1 for p in PAIRS if winner[p] == w) for w in ("plain", "studio", "tie")}
mean = {a: sum(score(*p, a) for p in PAIRS) / len(PAIRS) for a in ARM}


def get(model, task, arm, field):
    return runs[(model, task, arm)].get(field) or 0


def tot(model, arm, field):
    return sum(get(model, t, arm, field) for m, t in ALL if m == model)


def avg(model, arm):
    values = [score(model, t, arm) for m, t in PAIRS if m == model]
    return sum(values) / len(values) if values else None


def model_rows(model):
    tasks = [t for m, t in ALL if m == model]
    out = ""
    for arm in ARM:
        head = (f"<th scope='rowgroup' rowspan='2'>{NAME[model]}<span>{len(tasks)} request"
                f"{'s' if len(tasks) > 1 else ''}</span></th>") if arm == "plain" else ""
        won = sum(1 for t in tasks if winner.get((model, t)) == arm)
        cost = tot(model, arm, "cost_usd")
        mark = avg(model, arm)
        out += (f"<tr class='{arm}'>{head}<td><i class='dot {arm}'></i> {ARM[arm]}</td>"
                f"<td>{'n/a' if mark is None else f'{mark:.1f}'}</td><td>{won} of {len(tasks)}</td>"
                f"<td>{tot(model, arm, 'wall_s'):.0f} s</td><td>{tot(model, arm, 'api_s'):.0f} s</td>"
                f"<td>{k(tot(model, arm, 'output_tokens'))}</td><td>{k(tot(model, arm, 'input_tokens'))}</td>"
                f"<td>{f'${cost:.2f}' if cost else 'free tier'}</td>"
                f"<td>{tot(model, arm, 'tool_errors')} of {tot(model, arm, 'tool_calls')}</td></tr>")
    return out


def cards(prefix, folder):
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for model, task in ALL:
        verdict, sides = jd(model, task), ""
        slug = model.replace(".", "-")
        for arm in ARM:
            run = runs[(model, task, arm)]
            frames = []
            for index, shot in enumerate(run.get("shots", []), 1):
                image = Image.open(run["dir"] / shot).convert("RGB")
                image.thumbnail((560, 560))
                name = f"v2-{slug}__{task}-{arm}-{index:02d}.jpg"
                image.save(folder / name, quality=80)
                frames.append(prefix + name)
            mark = score(model, task, arm)
            picture = (f"<div class='show' data-frames='{','.join(frames)}'><img src='{frames[-1]}' loading='lazy' "
                       f"alt='{ARM[arm]} renders for {TASKS[task]} by {NAME[model]}, from first to final'>"
                       f"<span class='count'>Render {len(frames)} of {len(frames)}</span></div>") if frames else \
                "<div class='show none'>No picture was produced</div>"
            stop = {"error_max_turns": "it used all 40 turns", "turn limit": "it used all 9 turns"}.get(
                run.get("stop"), str(run.get("stop") or run.get("crashed")))
            note = "" if run.get("finished") else f"<li class='warn'>Did not finish: {html.escape(stop)}</li>"
            best = "<em>judged better</em>" if verdict.get("winner") == arm else ""
            sides += (f"<div class='side'><h4><i class='dot {arm}'></i>{ARM[arm]}{best}</h4>{picture}"
                      f"<ul><li>Judge: {'n/a' if mark is None else f'{mark:.1f} / 10'}</li>"
                      f"<li>{run.get('wall_s', 0):.0f} s total, {run.get('api_s', 0):.0f} s on the model</li>"
                      f"<li>{k(run.get('output_tokens', 0))} tokens written, {k(run.get('input_tokens', 0))} read</li>"
                      f"<li>{run.get('tool_calls', 0)} tool calls, {run.get('tool_errors', 0)} failed</li>{note}</ul></div>")
        reasons = [v.get("reason") for v in verdict.get("verdicts", []) if v.get("reason")]
        reason = f"<p class='reason'>Judge: “{html.escape(reasons[0])}”</p>" if reasons else ""
        split = verdict.get("wins", {})
        tie = "<p class='reason'>The judge disagreed with itself when the order was swapped, so this counts as a tie.</p>" \
            if split and max(split.values()) < 2 else ""
        out.append(f"<article class='card'><h3>{NAME[model]} <span>{TASKS[task]}</span></h3>"
                   f"<div class='sides'>{sides}</div>{reason}{tie}</article>")
    return "\n".join(out)


def charts():
    specs = [("Judge's overall score", "out of 10, average of two blind looks", lambda p, a: score(*p, a), lambda v: f"{v:.1f}", 10),
             ("Time waiting on the model", "seconds", lambda p, a: get(*p, a, "api_s"), lambda v: f"{v:.0f} s", None),
             ("Tokens read by the model", "thousands, across all its requests", lambda p, a: get(*p, a, "input_tokens"), k, None),
             ("Tool calls that failed", "count", lambda p, a: get(*p, a, "tool_errors"), lambda v: f"{v:.0f}", None)]
    figures = []
    for title, unit, value_of, fmt, fixed in specs:
        top = fixed or max(value_of(p, a) or 0 for p in PAIRS for a in ARM) or 1
        body = ""
        for p in PAIRS:
            bars = ""
            for arm in ARM:
                value = value_of(p, arm) or 0
                width = 0 if not value else max(1.5, 100 * value / top)
                bars += (f"<div class='bar-row' title='{ARM[arm]}: {fmt(value)}'><span class='track'><span class='bar {arm}' "
                         f"style='width:{width:.1f}%'></span></span><span class='val'>{fmt(value)}</span></div>")
            body += (f"<div class='pair-row'><div class='pair-name'>{NAME[p[0]]}<span>{TASKS[p[1]]}</span></div>"
                     f"<div class='bars'>{bars}</div></div>")
        figures.append(f"<figure class='chart'><figcaption><b>{title}</b><span>{unit}</span></figcaption>{body}</figure>")
    return "\n".join(figures)


def before_after():
    body = ""
    for model in MODELS:
        if model not in BEFORE or avg(model, "studio") is None:
            continue
        p0, s0 = BEFORE[model]
        body += (f"<tr><th scope='row'>{NAME[model]}</th><td>{p0:.1f}</td><td>{s0:.1f}</td>"
                 f"<td>{avg(model, 'plain'):.1f}</td><td>{avg(model, 'studio'):.1f}</td></tr>")
    return ("<div class='scroll'><table><thead><tr><th scope='col'>Judge's average, of 10</th>"
            "<th scope='col'>Plain, first round</th><th scope='col'>Tools, first round</th>"
            "<th scope='col'>Plain, now</th><th scope='col'>Tools, now</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


facts = {"pairs": len(PAIRS), "unscored": UNSCORED, "wins": wins, "mean": mean,
         "failed": {a: [sum(tot(m, a, "tool_errors") for m in MODELS), sum(tot(m, a, "tool_calls") for m in MODELS)] for a in ARM}}
for model in MODELS:
    facts[NAME[model]] = {
        "score": {a: avg(model, a) for a in ARM}, "before": BEFORE.get(model),
        "winner": {t: winner.get((model, t)) for m, t in ALL if m == model},
        **{f: {a: round(tot(model, a, f), 2) for a in ARM} for f in ("cost_usd", "wall_s", "api_s", "input_tokens", "output_tokens")},
        "failed": {a: [tot(model, a, "tool_errors"), tot(model, a, "tool_calls")] for a in ARM},
        "runs": {f"{t} {a}": [score(model, t, a), runs[(model, t, a)].get("stop"), runs[(model, t, a)].get("renders")]
                 for m, t in ALL if m == model for a in ARM}}
print(json.dumps(facts, indent=1))
if len(sys.argv) < 5:
    sys.exit(0)
text = json.loads(Path(sys.argv[4]).read_text())
rows = "".join(model_rows(m) for m in MODELS)


def fixes(prefix, tag_open, plain_lists):
    ul = "<ul>" if plain_lists else '<ul class="plain">'
    trio = ""
    for task, name in TASKS.items():
        trio += (f"<article class='card'><h3>Claude Opus 5.5 <span>{name}</span></h3><div class='trio'>"
                 + "".join(f"<div class='side'><h4><i class='dot {dot}'></i>{label}</h4><div class='show'>"
                           f"<img src='{prefix}fix-{task}-{key}.jpg' loading='lazy' alt='Opus {label.lower()} for {name}'></div></div>"
                           for key, label, dot in (("plain", "Plain Blender", "plain"), ("before", "Tools, first round", "studio"),
                                                   ("after", "Tools, after the fixes", "studio")))
                 + "</div></article>")
    return f"""{tag_open}
    <div class="stack" style="display:flex;flex-direction:column;gap:20px">
      <h2>What changed between the two rounds.</h2>
      <p>{text['fix_intro']}</p>
      {ul}
{chr(10).join('        <li>' + item + '</li>' for item in text['fix_list'])}
      </ul>
      {before_after()}
      <p class="note">{text['fix_note']}</p>
      <div class="cards">{trio}</div>
    </div>
  </section>
"""


TRIO_CSS = ("\n.trio { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }\n"
            ".trio .show { aspect-ratio: 4 / 5; }\n.trio .show img { width: 100%; height: 100%; object-fit: contain; }\n"
            "@media (max-width: 640px) { .trio { grid-template-columns: 1fr; } }\n")

# ---- artifact page ------------------------------------------------------
out_artifact.mkdir(parents=True, exist_ok=True)
page = (HERE / "artifact_shell.html").read_text()
page = page[:page.index("<tbody>") + 7] + rows + page[page.index("</tbody>"):]
start = page.index("<div class=\"cards\">") + len("<div class=\"cards\">")
end = page.index("</div>\n  </section>\n\n  <section>\n    <h2>Run by run")
page = page[:start] + "\n" + cards("", out_artifact) + "\n    " + page[end:]
start = page.index("<div class=\"charts\">") + len("<div class=\"charts\">")
end = page.index("</div>\n  </section>\n\n  <section>\n    <h2>How it was run")
page = page[:start] + "\n" + charts() + "\n    " + page[end:]
page = re.sub(r"<p class=\"lede\">.*?</p>", lambda _: f"<p class=\"lede\">{text['verdict']}</p>", page, count=1, flags=re.S)
page = re.sub(r"<p class=\"muted\">The same model was given.*?</p>", lambda _: f"<p class=\"muted\">{text['intro']}</p>", page, count=1, flags=re.S)
start = page.index("<ul>", page.index("</table>"))
end = page.index("</ul>", start) + 5
page = page[:start] + "<ul>\n" + "\n".join(f"<li>{f}</li>" for f in text["findings"]) + "\n</ul>" + page[end:]
for heading, items in (("<h2>How it was run</h2>", text["method"]), ("<h2>What this does not show</h2>", text["caveats"])):
    start = page.index("<ul>", page.index(heading))
    end = page.index("</ul>", start) + 5
    page = page[:start] + "<ul>\n" + "\n".join(f"      <li>{c}</li>" for c in items) + "\n    </ul>" + page[end:]
anchor = "  <section>\n    <h2>Run by run</h2>"
page = page.replace(anchor, fixes("", "  <section>", True) + "\n" + anchor)
page = page.replace("</style>", TRIO_CSS + "main > *, section > * { min-width: 0; }\n</style>", 1)
assert "{{" not in page
(out_artifact / "blender-benchmark.html").write_text(page)
for image in HERE.glob("fix-*.jpg"):
    (out_artifact / image.name).write_bytes(image.read_bytes())

# ---- site ---------------------------------------------------------------
bench = site_docs / "bench"
site = (HERE / "site_template.html").read_text()
values = {"{{SUMMARY_ROWS}}": rows, "{{CARDS}}": cards("bench/", bench), "{{SHORT}}": text["short"],
          "{{SHOWS}}": "\n".join(f"            <li>{f}</li>" for f in text["findings"]),
          "{{NOT_SHOWN}}": "\n".join(f"            <li>{c}</li>" for c in text["caveats"]),
          "{{CARD_NOTE}}": text["card_note"], "{{COMPARE_INTRO}}": text["intro"],
          "{{HERO_RESULT}}": text["hero"]}
for key, value in values.items():
    assert key in site, key
    site = site.replace(key, value)
anchor = '  <section id="gemini">'
site = site.replace(anchor, fixes("bench/", '  <section id="fixes">', False) + "\n" + anchor)
site = site.replace("</style>", TRIO_CSS + "</style>", 1)
assert "{{" not in site
(site_docs / "index.html").write_text(site)
used = set(re.findall(r"bench/([\w.-]+\.jpg)", site))
for image in bench.glob("*.jpg"):
    if image.name not in used:
        image.unlink()
print("built:", len(PAIRS), "pairs;", len(list(out_artifact.glob('*.jpg'))), "artifact images;", len(list(bench.glob('*.jpg'))), "site images")
