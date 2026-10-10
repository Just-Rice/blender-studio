"""Plain Blender with nothing added: run code, list objects, render. Used as the benchmark baseline."""
import contextlib
import io
import math

import bpy

from .. import state
from ..commands import command


@command(mutates=False)
def raw_python(code):
    stdout = io.StringIO()
    namespace = {"bpy": bpy, "__name__": "__main__"}
    with contextlib.redirect_stdout(stdout):
        exec(compile(code, "<execute_python>", "exec"), namespace)
    return {"output": stdout.getvalue()[-4000:]}


@command(mutates=False)
def raw_scene_info():
    scene = bpy.context.scene
    return {
        "blender_version": bpy.app.version_string,
        "objects": [{"name": o.name, "type": o.type, "location": [round(v, 3) for v in o.location],
                     "rotation_deg": [round(math.degrees(v), 1) for v in o.rotation_euler],
                     "dimensions": [round(v, 3) for v in o.dimensions]} for o in list(scene.objects)[:100]],
        "active_camera": scene.camera.name if scene.camera else None,
        "render_engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
    }


@command(mutates=False)
def raw_render():
    scene = bpy.context.scene
    if scene.camera is None:
        raise ValueError("The scene has no active camera.")
    settings = scene.render.image_settings
    if hasattr(settings, "media_type"):
        settings.media_type = "IMAGE"
    settings.file_format = "PNG"
    scene.render.filepath = state.render_path("render")
    bpy.ops.render.render(write_still=True)
    return {"path": scene.render.filepath}
