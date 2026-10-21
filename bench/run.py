"""Benchmark: the same model, the same request, with plain Blender scripting versus Blender Studio's tools.

    uv run python bench/run.py OUT --claude claude-haiku-4-5-20251001,claude-sonnet-5-5 --tasks mug,camp,robot
    GEMINI_API_KEY=... uv run python bench/run.py OUT --gemini gemini-3.6-flash:mug

Each run gets its own Blender and writes OUT/<model>__<task>__<arm>/metrics.json plus every render the
model looked at. Runs that already have a metrics.json are skipped, so the command can be repeated.
"""
import argparse
import asyncio
import base64
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
ARMS = {
    "plain": [PYTHON, str(ROOT / "bench" / "baseline_server.py")],
    "studio": [PYTHON, "-m", "blender_studio.server"],
}
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tasks import REGULAR, TASKS as SUITE  # noqa: E402

TASKS = {name: task["brief"] for name, task in SUITE.items()}
USAGE_LIMIT = 0.8      # stop starting new runs once the Claude plan's usage window is this full
SYSTEM = ("You are a 3D artist working in Blender through the tools provided. Make the picture the user asks "
          "for; you cannot ask the user anything. Look at a render of your work and improve it until you are "
          "satisfied. Your last render is taken as the finished picture. Finish with one sentence describing it.")
CLAUDE_MAX_TURNS = 40
GEMINI_MAX_TURNS = 9   # the free tier allows about 20 requests per model per day, shared by both arms
TIMEOUT = 1500
GEMINI_RUN_LIMIT = 1200  # seconds; a Gemini run that has not finished by then is stopped


def server_config(arm, run_dir):
    return {"command": ARMS[arm][0], "args": ARMS[arm][1:],
            "env": {"BLENDER_STUDIO_HOME": str(run_dir / "blender")}}


def save_image(run_dir, count, data):
    path = run_dir / f"shot-{count:02d}.jpg"
    path.write_bytes(base64.b64decode(data))
    return path.name


def run_claude(model, task, arm, run_dir):
    config = run_dir / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"blender": server_config(arm, run_dir)}}))
    command = ["claude", "-p", TASKS[task], "--model", model, "--mcp-config", str(config), "--strict-mcp-config",
               "--tools", "", "--allowedTools", "mcp__blender", "--system-prompt", SYSTEM,
               "--disable-slash-commands", "--setting-sources", "project", "--output-format", "stream-json",
               "--verbose", "--max-turns", str(CLAUDE_MAX_TURNS), "--no-session-persistence"]
    # A session started from inside another must not inherit its identity or effort setting.
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    started = time.time()
    with open(run_dir / "stream.jsonl", "wb") as stream:
        try:
            subprocess.run(command, cwd=run_dir, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=TIMEOUT)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
    wall = time.time() - started

    metrics = {"family": "claude", "model": model, "task": task, "arm": arm, "wall_s": round(wall, 1),
               "tool_calls": 0, "tool_errors": 0, "renders": 0, "tools_used": {}, "shots": [], "errors": [],
               "timed_out": timed_out, "said": ""}
    names = {}
    for line in (run_dir / "stream.jsonl").read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        blocks = event.get("message", {}).get("content", []) if event.get("type") in ("assistant", "user") else []
        for block in blocks if isinstance(blocks, list) else []:
            if block.get("type") == "tool_use":
                name = block["name"].split("__")[-1]
                names[block["id"]] = name
                metrics["tool_calls"] += 1
                metrics["last_call"] = "render" if call["name"] in ("render_image", "render_preview", "render_final",
                                                                     "render_frames", "render_animation") else "other"
                metrics["tools_used"][name] = metrics["tools_used"].get(name, 0) + 1
            elif block.get("type") == "tool_result":
                content = block.get("content") if isinstance(block.get("content"), list) else []
                if block.get("is_error"):
                    metrics["tool_errors"] += 1
                    text = " ".join(c.get("text", "") for c in content if c.get("type") == "text") \
                        or str(block.get("content"))
                    metrics["errors"].append({"tool": names.get(block.get("tool_use_id")), "error": text[:300]})
                for item in content:
                    if item.get("type") == "image":
                        metrics["renders"] += 1
                        metrics["shots"].append(save_image(run_dir, metrics["renders"], item["source"]["data"]))
        if event.get("type") == "rate_limit_event":
            windows = event.get("rate_limit_info", {}).get("unifiedWindows", {})
            used = max([w.get("utilization") or 0 for w in windows.values()] or [0])
            metrics["usage"] = max(metrics.get("usage", 0), used)
        if event.get("type") == "result":
            usage = event.get("usage", {})
            metrics.update(
                requests=event.get("num_turns"), api_s=round(event.get("duration_api_ms", 0) / 1000, 1),
                input_tokens=usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                + usage.get("cache_creation_input_tokens", 0),
                fresh_input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0), cost_usd=event.get("total_cost_usd"),
                finished=event.get("subtype") == "success" and not event.get("is_error"),
                stop=event.get("subtype"), said=(event.get("result") or "")[-600:])
    metrics.setdefault("finished", False)
    return metrics


def gemini_schema(schema):
    if "anyOf" in schema:
        options = [o for o in schema["anyOf"] if o.get("type") != "null"]
        arrays = [o for o in options if o.get("type") == "array"]
        strings = [o for o in options if o.get("type") == "string"]
        pick = strings[0] if arrays and strings and arrays[0].get("items", {}).get("type") == "number" \
            else (arrays or options)[0]
        return gemini_schema({**pick, **({"description": schema["description"]} if "description" in schema else {})})
    out = {key: schema[key] for key in ("type", "description", "enum") if key in schema}
    if "items" in schema:
        out["items"] = gemini_schema(schema["items"])
    if schema.get("type") == "object":
        if "properties" in schema:
            out["properties"] = {name: gemini_schema(prop) for name, prop in schema["properties"].items()}
            if schema.get("required"):
                out["required"] = schema["required"]
        elif "additionalProperties" in schema:
            # Gemini has no free-form maps; pass them as JSON text and decode before the call.
            return {"type": "string", "description": schema.get("description", "") + " (a JSON object as text)"}
    return out


def ask_gemini(model, key, body):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(8):
        request = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            if error.code == 400 and "thinking" in detail.lower() and "generationConfig" in body:
                del body["generationConfig"]
                continue
            hours = "retry in" in detail and "h" in detail.split("Please retry in ")[-1].split("s.")[0]
            if error.code == 429 and hours:
                raise RuntimeError(f"daily allowance for {model} used up") from None
            if error.code in (429, 500, 503) and attempt < 7:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini {error.code}: {detail[:300]}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            # A dropped or slow connection is not a result; try again.
            if attempt < 7:
                time.sleep(10)
                continue
            raise RuntimeError(f"network: {error}") from None


async def run_gemini_async(model, task, arm, run_dir):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    key = os.environ["GEMINI_API_KEY"]
    config = server_config(arm, run_dir)
    metrics = {"family": "gemini", "model": model, "task": task, "arm": arm, "tool_calls": 0, "tool_errors": 0,
               "renders": 0, "tools_used": {}, "shots": [], "errors": [], "requests": 0, "input_tokens": 0,
               "output_tokens": 0, "api_s": 0.0, "finished": False, "said": "", "timed_out": False}
    started = time.time()
    server = StdioServerParameters(command=config["command"], args=config["args"],
                                   env={**os.environ, **config["env"]}, cwd=str(ROOT))
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        text_maps = {t.name: [n for n, p in t.inputSchema.get("properties", {}).items()
                              if "additionalProperties" in json.dumps(p)] for t in tools}
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM + f" You have at most {GEMINI_MAX_TURNS} turns, "
                                             "so call several tools in each turn."}]},
            "contents": [{"role": "user", "parts": [{"text": TASKS[task]}]}],
            "tools": [{"functionDeclarations": [{"name": t.name, "description": t.description,
                                                 "parameters": gemini_schema(t.inputSchema)} for t in tools]}],
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}},
        }
        for _ in range(GEMINI_MAX_TURNS):
            if time.time() - started > GEMINI_RUN_LIMIT:
                metrics["stop"] = "time limit"
                break
            asked = time.time()
            try:
                reply = ask_gemini(model, key, body)
            except RuntimeError as error:
                metrics["stop"] = str(error)
                break
            metrics["api_s"] += time.time() - asked
            metrics["requests"] += 1
            usage = reply.get("usageMetadata", {})
            metrics["input_tokens"] += usage.get("promptTokenCount", 0)
            metrics["output_tokens"] += usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
            candidate = (reply.get("candidates") or [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            said = " ".join(p["text"] for p in parts if "text" in p and not p.get("thought")).strip()
            calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not calls:
                metrics["finished"] = bool(parts)
                metrics["said"] = said[-600:]
                metrics.setdefault("stop", candidate.get("finishReason", "no reply"))
                break
            body["contents"].append(candidate["content"])
            answers, pictures = [], []
            for call in calls:
                args = dict(call.get("args") or {})
                for name in text_maps.get(call["name"], []):
                    if isinstance(args.get(name), str):
                        try:
                            args[name] = json.loads(args[name])
                        except ValueError:
                            pass
                result = await session.call_tool(call["name"], args)
                text = "\n".join(c.text for c in result.content if c.type == "text")
                metrics["tool_calls"] += 1
                metrics["last_call"] = "render" if call["name"] in ("render_image", "render_preview", "render_final",
                                                                     "render_frames", "render_animation") else "other"
                metrics["tools_used"][call["name"]] = metrics["tools_used"].get(call["name"], 0) + 1
                if result.isError:
                    metrics["tool_errors"] += 1
                    metrics["errors"].append({"tool": call["name"], "error": text[:300]})
                for item in result.content:
                    if item.type == "image":
                        metrics["renders"] += 1
                        metrics["shots"].append(save_image(run_dir, metrics["renders"], item.data))
                        pictures.append({"inlineData": {"mimeType": item.mimeType, "data": item.data}})
                answer = {"name": call["name"], "response": {"result": text[:6000]}}
                if "id" in call:
                    answer["id"] = call["id"]
                answers.append({"functionResponse": answer})
            body["contents"].append({"role": "user", "parts": answers + pictures})
        else:
            metrics["stop"] = "turn limit"
        if not metrics["shots"] or metrics.get("last_call") != "render":
            # Gemini's free allowance caps the turns, and it often spends them all before rendering.
            # Photograph the scene as it was left, the same way on both arms, so there is always a picture.
            closing = "render_image" if arm == "plain" else "render_preview"
            result = await session.call_tool(closing, {})
            for item in result.content:
                if item.type == "image":
                    metrics["renders"] += 1
                    metrics["shots"].append(save_image(run_dir, metrics["renders"], item.data))
                    metrics["closing_render"] = True
    metrics["wall_s"] = round(time.time() - started, 1)
    metrics["api_s"] = round(metrics["api_s"], 1)
    return metrics


def run_one(family, model, task, arm, out):
    run_dir = out / f"{model}__{task}__{arm}"
    done = run_dir / "metrics.json"
    if done.exists():
        # Finished earlier: reuse it, but its usage reading is out of date and must not trigger a pause.
        return {**json.loads(done.read_text()), "usage": 0}
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"start  {model} {task} {arm}", flush=True)
    try:
        if family == "claude":
            metrics = run_claude(model, task, arm, run_dir)
        else:
            metrics = asyncio.run(run_gemini_async(model, task, arm, run_dir))
    except Exception as error:  # a crashed run is a result too
        metrics = {"family": family, "model": model, "task": task, "arm": arm, "finished": False,
                   "crashed": "; ".join(f"{type(e).__name__}: {e}" for e in getattr(error, "exceptions", [error]))[:600],
                   "shots": [], "renders": 0}
    if metrics.get("family") == "claude" and not metrics.get("tool_calls") and metrics.get("usage", 0) >= 0.99:
        # Turned away by the usage limit before doing anything: not a result, so leave it to be run again.
        print(f"refused {model} {task} {arm}: usage limit reached", flush=True)
        shutil.rmtree(run_dir, ignore_errors=True)
        return metrics
    done.write_text(json.dumps(metrics, indent=1))
    print(f"done   {model} {task} {arm}: {metrics.get('wall_s')}s, {metrics.get('tool_calls')} calls, "
          f"{metrics.get('tool_errors')} errors, {metrics.get('renders')} renders, "
          f"finished={metrics.get('finished')} {metrics.get('stop', '')} {metrics.get('crashed', '')}", flush=True)
    return metrics


def copy_cached_plain(sources, out, models, tasks):
    """Plain Blender does not change between cycles, so its runs can be reused instead of paid for again."""
    import shutil
    copied = 0
    for source in sources:
        for model in models:
            for task in tasks:
                name = f"{model}__{task}__plain"
                if (Path(source) / name / "metrics.json").exists() and not (out / name).exists():
                    shutil.copytree(Path(source) / name, out / name)
                    copied += 1
    return copied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--claude", default="")
    parser.add_argument("--gemini", default="", help="model:task pairs, comma separated")
    parser.add_argument("--tasks", default=",".join(REGULAR))
    parser.add_argument("--plain-from", default="", help="earlier run folders to reuse plain-Blender runs from")
    parser.add_argument("--arms", default="plain,studio")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    models, tasks, arms = (list(filter(None, x.split(","))) for x in (args.claude, args.tasks, args.arms))
    unknown = [t for t in tasks if t not in TASKS]
    if unknown:
        raise SystemExit(f"Unknown tasks: {', '.join(unknown)}. Known: {', '.join(TASKS)}")
    if args.plain_from:
        print("reused plain runs:", copy_cached_plain(args.plain_from.split(","), args.out, models, tasks), flush=True)
    for model in models:
        for task in tasks:
            # Both arms at once, so they share the machine equally.
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda arm: run_one("claude", model, task, arm, args.out), arms))
            used = max(r.get("usage", 0) for r in results)
            if used >= USAGE_LIMIT:
                print(f"PAUSED: the Claude plan's usage window is {used:.0%} full. Run the same command again "
                      "later; finished runs are skipped.", flush=True)
                raise SystemExit(3)
    for pair in filter(None, args.gemini.split(",")):
        model, task = pair.split(":")
        for arm in arms:
            run_one("gemini", model, task, arm, args.out)


if __name__ == "__main__":
    main()
