"""Benchmark baseline: Blender as an AI normally gets it. Three tools: list the scene, run Python, render."""
import io
import json
import os

os.environ["BLENDER_STUDIO_KEEP_SCENE"] = "1"

from mcp.server.fastmcp import FastMCP, Image  # noqa: E402
from PIL import Image as PILImage  # noqa: E402

from blender_studio.launcher import Blender, BlenderError  # noqa: E402

mcp = FastMCP("blender", instructions="Blender is running with its default startup scene (a cube, a light and "
              "a camera). Run Python in it with execute_python and look at the camera view with render_image.")
blender = Blender()


def call(cmd, **args):
    try:
        return blender.call(cmd, **args)
    except BlenderError as exc:
        raise ValueError(str(exc)) from None


@mcp.tool()
def get_scene_info() -> dict:
    """List the objects in the scene with their type, position and size, plus the camera and render settings."""
    return call("raw_scene_info")


@mcp.tool()
def execute_python(code: str) -> dict:
    """Run Python code inside Blender. `bpy` is already imported. Returns whatever the code prints."""
    return call("raw_python", code=code)


@mcp.tool()
def render_image() -> list:
    """Render the scene from the active camera with the current render settings and return the picture."""
    result = call("raw_render")
    image = PILImage.open(result["path"]).convert("RGB")
    image.thumbnail((1280, 1280))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    return [Image(data=buffer.getvalue(), format="jpeg"), json.dumps({"saved_to": result["path"]})]


if __name__ == "__main__":
    mcp.run()
