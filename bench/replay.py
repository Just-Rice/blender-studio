"""Replay the tool calls recorded in a benchmark run against the current tools, and render the result.

    uv run python bench/replay.py RUN_DIR OUT.jpg [--final]

Lets a change to the tools be checked on a model's exact scene without asking the model again.
Calls that only look (previews, sheets, checks, the guide) are skipped; one render is taken at the end.
"""
import asyncio
import base64
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

LOOK_ONLY = {"render_preview", "render_final", "render_animation", "contact_sheet", "design_guide", "list_presets",
             "scene_info", "scene_check", "open_in_blender", "save_blend"}


def recorded_calls(run_dir):
    calls = []
    for line in (run_dir / "stream.jsonl").read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "assistant":
            for block in event["message"]["content"]:
                if block.get("type") == "tool_use":
                    calls.append((block["name"].split("__")[-1], block["input"]))
    return calls


async def replay(run_dir, out, final):
    server = StdioServerParameters(command=sys.executable, args=["-m", "blender_studio.server"])
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        for name, args in recorded_calls(run_dir):
            if name in LOOK_ONLY:
                continue
            result = await session.call_tool(name, args)
            if result.isError:
                print("replay error:", name, result.content[0].text[:200])
        check = await session.call_tool("scene_check", {})
        print(check.content[0].text[:700])
        shot = await session.call_tool("render_final" if final else "render_preview",
                                       {"samples": 96} if final else {"quality": "preview"})
        for item in shot.content:
            if item.type == "image":
                Path(out).write_bytes(base64.b64decode(item.data))
            else:
                print(item.text[:300])


if __name__ == "__main__":
    asyncio.run(replay(Path(sys.argv[1]), sys.argv[2], "--final" in sys.argv))
