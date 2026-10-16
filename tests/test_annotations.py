"""Every tool must declare all four MCP hints as real booleans (directories reject tools that do not).

    uv run python tests/test_annotations.py
"""
import asyncio

from blender_studio import server

HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


def test_every_tool_has_all_four_hints():
    tools = asyncio.run(server.mcp.list_tools())
    missing = []
    for tool in tools:
        notes = tool.annotations
        for hint in HINTS:
            if notes is None or not isinstance(getattr(notes, hint, None), bool):
                missing.append(f"{tool.name}.{hint}")
    assert not missing, "Missing or non-boolean hints: " + ", ".join(missing)
    assert set(server.HINTS) == {tool.name for tool in tools}, "HINTS and the tool list have drifted apart"


def test_read_only_tools_are_not_destructive():
    for tool in asyncio.run(server.mcp.list_tools()):
        if tool.annotations.readOnlyHint:
            assert not tool.annotations.destructiveHint, tool.name


if __name__ == "__main__":
    test_every_tool_has_all_four_hints()
    test_read_only_tools_are_not_destructive()
    print("all 43 tools declare all four hints")
