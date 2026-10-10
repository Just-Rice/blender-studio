"""A small preview of Blender Studio driven by Google Gemini instead of Claude.

Gemini is given a cut-down set of the tools (no run_python, no file access) and a step limit, builds a
scene, looks at its own renders and improves them. Everything it does is written to OUT_DIR.

    GEMINI_API_KEY=... uv run python examples/gemini_demo.py OUT_DIR "a toy rocket on a launch pad"
"""
import asyncio
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from blender_studio.server import GUIDE, INSTRUCTIONS

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
API = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
# The free tier allows roughly 20 requests per model per day, so a run has to fit well inside that.
MAX_TURNS = int(os.environ.get("GEMINI_MAX_TURNS", "10"))
THINKING = os.environ.get("GEMINI_THINKING", "low")
TOOLS = {"list_presets", "scene_info", "create_object", "transform_object", "delete_objects", "apply_material",
         "add_polish", "add_backdrop", "studio_lighting", "frame_camera", "set_look", "scene_check",
         "render_preview", "contact_sheet", "undo"}
BRIEF = f"""You are a 3D artist using Blender Studio.

{INSTRUCTIONS}

This is a cut-down preview: there is no run_python and no render_final, so build from the basic shapes
(scale and rotate them inventively) and treat render_preview as your final output. You have only
{MAX_TURNS} turns, so call many tools in each turn: build the whole subject in your first turn or two,
then materials, backdrop, lighting and camera together, then render. Keep the model to about 15 parts.
Do not call scene_info or list_presets; everything you need is below. After each render_preview you will be shown
the picture: say in one or two sentences what is wrong with it, then fix it. Render at least twice.
When you are happy, reply with a short description of the finished picture and no tool call.

{GUIDE}"""


def simplify(schema):
    """Gemini accepts a narrower schema dialect than MCP produces; reduce unions to one concrete type."""
    if "anyOf" in schema:
        options = [o for o in schema["anyOf"] if o.get("type") != "null"]
        arrays = [o for o in options if o.get("type") == "array"]
        strings = [o for o in options if o.get("type") == "string"]
        if arrays and strings and arrays[0].get("items", {}).get("type") == "number":
            pick = strings[0]            # colour: '#rrggbb' or [r, g, b]
        else:
            pick = (arrays or options)[0]  # names or scale: a list covers the single case too
        merged = {**pick}
        if "description" in schema:
            merged["description"] = schema["description"]
        return simplify(merged)
    out = {}
    for key in ("type", "description", "enum"):
        if key in schema:
            out[key] = schema[key]
    if "items" in schema:
        out["items"] = simplify(schema["items"])
    if "properties" in schema:
        out["properties"] = {name: simplify(prop) for name, prop in schema["properties"].items()}
        if schema.get("required"):
            out["required"] = schema["required"]
    return out


def ask_gemini(key, contents, declarations):
    request_body = {
        "systemInstruction": {"parts": [{"text": BRIEF}]},
        "contents": contents,
        "tools": [{"functionDeclarations": declarations}],
    }
    if THINKING:
        # Long private reasoning makes each turn take minutes; the craft rules are already spelled out.
        request_body["generationConfig"] = {"thinkingConfig": {"thinkingLevel": THINKING}}
    body = json.dumps(request_body).encode()
    for attempt in range(6):
        request = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json",
                                                                  "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            if error.code == 400 and "thinking" in detail.lower() and "generationConfig" in request_body:
                del request_body["generationConfig"]
                body = json.dumps(request_body).encode()
                continue
            if error.code == 429 and "free_tier_requests" in detail:
                # A daily allowance, not a momentary spike: waiting will not help.
                wait = detail.split("Please retry in ")[-1].split('"')[0].strip(". ") if "retry in" in detail else "?"
                raise RuntimeError(f"The free daily allowance for {MODEL} is used up (resets in {wait}). "
                                   "Set GEMINI_MODEL to another model or try again later.") from None
            if error.code in (429, 500, 503) and attempt < 5:
                print(f"    (Gemini is busy, code {error.code}; waiting {8 * (attempt + 1)}s)", flush=True)
                time.sleep(8 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini returned {error.code}: {detail[:600]}") from None


async def run(out, prompt):
    key = os.environ["GEMINI_API_KEY"]
    log = {"model": MODEL, "prompt": prompt, "turns": [], "started": time.strftime("%Y-%m-%d %H:%M")}
    server = StdioServerParameters(command=sys.executable, args=["-m", "blender_studio.server"])
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        declarations = [
            {"name": tool.name, "description": tool.description, "parameters": simplify(tool.inputSchema)}
            for tool in (await session.list_tools()).tools if tool.name in TOOLS
        ]
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        shot = 0
        reply = {}
        for turn in range(MAX_TURNS):
            asked = time.time()
            try:
                reply = ask_gemini(key, contents, declarations)
            except RuntimeError as error:
                log["stopped"] = str(error)
                print(f"    stopped: {error}", flush=True)
                break
            print(f"    (Gemini answered in {time.time() - asked:.0f}s)", flush=True)
            candidate = (reply.get("candidates") or [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            said = " ".join(p["text"] for p in parts if "text" in p and not p.get("thought")).strip()
            calls = [p["functionCall"] for p in parts if "functionCall" in p]
            entry = {"said": said, "calls": []}
            log["turns"].append(entry)
            print(f"\n[{turn + 1}] {said[:300]}", flush=True)
            if not calls:
                if not parts:
                    entry["said"] = f"(Gemini stopped: {candidate.get('finishReason', 'no reply')})"
                break
            contents.append(candidate["content"])
            answers, pictures = [], []
            for call in calls:
                args = call.get("args") or {}
                result = await session.call_tool(call["name"], args)
                text = "\n".join(c.text for c in result.content if c.type == "text")
                record = {"tool": call["name"], "args": args, "error": bool(result.isError), "result": text[:1500]}
                for item in result.content:
                    if item.type == "image":
                        shot += 1
                        record["image"] = f"shot-{shot:02d}.jpg"
                        (out / record["image"]).write_bytes(base64.b64decode(item.data))
                        pictures.append({"inlineData": {"mimeType": item.mimeType, "data": item.data}})
                entry["calls"].append(record)
                print(f"    {'ERR' if result.isError else 'ok '} {call['name']} {json.dumps(args)[:140]}", flush=True)
                answer = {"name": call["name"], "response": {"result": text[:4000]}}
                if "id" in call:
                    answer["id"] = call["id"]
                answers.append({"functionResponse": answer})
            contents.append({"role": "user", "parts": answers + pictures})
            (out / "transcript.json").write_text(json.dumps(log, indent=1))
        log["last_turn_tokens"] = reply.get("usageMetadata", {}).get("totalTokenCount")
        last_calls = [c for t in log["turns"] for c in t["calls"]]
        if last_calls and not last_calls[-1].get("image") and last_calls[-1]["tool"] != "render_preview":
            # Gemini ran out of turns after its last change; photograph the scene as it left it.
            result = await session.call_tool("render_preview", {"quality": "preview"})
            for item in result.content:
                if item.type == "image":
                    shot += 1
                    (out / f"shot-{shot:02d}.jpg").write_bytes(base64.b64decode(item.data))
                    log["closing_shot"] = f"shot-{shot:02d}.jpg"
    log["finished"] = time.strftime("%Y-%m-%d %H:%M")
    (out / "transcript.json").write_text(json.dumps(log, indent=1))
    print(f"\nDone. {shot} pictures and transcript.json are in {out}")


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    asyncio.run(run(folder, sys.argv[2] if len(sys.argv) > 2
                    else "A cheerful toy rocket standing on a launch pad, as a product shot for a toy catalogue."))
