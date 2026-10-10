"""Live window mode: Blender opens visibly and the scene is built while you watch. Usage: live_window.py [seconds_to_hold]"""
import os
import sys
import time

os.environ["BLENDER_STUDIO_WINDOW"] = "1"
from blender_studio.launcher import Blender  # noqa: E402

hold = float(sys.argv[1]) if len(sys.argv) > 1 else 3
b = Blender()


def step(cmd, pause=0.6, **args):
    start = time.time()
    result = b.call(cmd, **args)
    print(f"ok {cmd:16s} {time.time() - start:5.1f}s  {str(result)[:150]}", flush=True)
    time.sleep(pause)
    return result


step("create_object", kind="cylinder", name="Body", scale=[0.3, 0.3, 0.6], location=[0, 0, 0.9])
step("create_object", kind="cone", name="Nose", scale=[0.3, 0.3, 0.3], location=[0, 0, 1.8])
step("create_object", kind="sphere", name="Window", scale=0.12, location=[0, -0.26, 1.1])
step("apply_material", objects="Body", preset="ceramic", color="#f2efe9")
step("apply_material", objects="Nose", preset="plastic_glossy", color="#d6332b")
step("apply_material", objects="Window", preset="glass")
step("add_polish", objects="Body", bevel=0.05)
step("add_backdrop", style="cyclorama", color="#27456b")
step("studio_lighting", style="three_point")
step("frame_camera", shot="three_quarter")
step("set_look", preset="vivid")
print(step("scene_check"))
print(step("run_python", code="""
area = next((a for w in bpy.context.window_manager.windows for a in w.screen.areas if a.type == 'VIEW_3D'), None)
if area:
    space = area.spaces.active
    space.region_3d.view_perspective = 'CAMERA'
    space.shading.type = 'MATERIAL'
result = {'background': bpy.app.background, 'windows': len(bpy.context.window_manager.windows), 'view3d': bool(area)}
"""))
time.sleep(hold)
if len(sys.argv) > 2:
    os.system(f"screencapture -x '{sys.argv[2]}'")
print("render:", step("render", quality="draft")["path"])
step("contact_sheet")
step("delete_objects", names="Nose")
print(step("undo"))
names = [o["name"] for o in step("scene_info")["objects"]]
print("after undo:", names)
assert "Nose" in names, "undo did not restore the object"
step("create_object", kind="sphere", name="Extra", scale=0.1, location=[1, 0, 0.1])
print("still responsive after undo: yes")
time.sleep(1)
b.close()
print("PASS")
