"""Talk to the server exactly as an AI app would, over MCP."""
import asyncio, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "blender_studio.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("instructions:", len(init.instructions or ""), "chars")
            tools = (await session.list_tools()).tools
            print(len(tools), "tools:", ", ".join(t.name for t in tools))
            async def call(tool, **args):
                r = await session.call_tool(tool, args)
                kinds = [c.type + (f"({len(c.data)//1024}KB)" if c.type == "image" else ": " + c.text[:150]) for c in r.content]
                print(("ERR " if r.isError else "ok  ") + tool, kinds)
            await call("create_object", kind="sphere", name="Ball", scale=0.5, location=[0, 0, 0.5])
            await call("apply_material", objects="Ball", preset="car_paint")
            await call("apply_material", objects="Ball", preset="nonsense")
            await call("scene_check")
            await call("add_backdrop")
            await call("studio_lighting", style="three_point")
            await call("frame_camera", shot="three_quarter")
            await call("render_preview", quality="draft")
            await call("contact_sheet")
            await call("design_guide")

asyncio.run(main())
