"""End-to-end check: start Blender, build a small scene with every tool family, render it."""
import sys, time
from blender_studio.launcher import Blender

b = Blender()
t = time.time()
def step(cmd, **a):
    t0 = time.time(); r = b.call(cmd, **a); print(f"{cmd:16s} {time.time()-t0:5.1f}s  {str(r)[:230]}"); return r

step("create_object", kind="cylinder", name="Mug", scale=[0.04, 0.04, 0.05], location=[0, 0, 0.05])
step("create_object", kind="torus", name="Handle", scale=[0.03, 0.03, 0.03], location=[0.045, 0, 0.05], rotation_deg=[90, 0, 0])
step("create_object", kind="sphere", name="Ball", scale=0.025, location=[-0.09, -0.03, 0.025])
step("create_object", kind="cube", name="Block", scale=[0.03, 0.03, 0.02], location=[0.11, -0.04, 0.02], rotation_deg=[0, 0, 25])
step("apply_material", objects=["Mug", "Handle"], preset="ceramic", color="#2f6f8f")
step("apply_material", objects="Ball", preset="gold")
step("apply_material", objects="Block", preset="wood")
step("add_polish", objects=["Mug", "Block"], bevel=0.04)
step("add_backdrop", style="cyclorama", color="#e8dfd2")
step("studio_lighting", style=sys.argv[1] if len(sys.argv) > 1 else "softbox")
step("frame_camera", shot="three_quarter", depth_of_field=4)
step("set_look", preset="product_clean")
step("scene_check")
print(step("render", quality="preview")["path"])
step("contact_sheet")
step("scene_info")
try: step("run_python", code="1/0")
except Exception as e: print("expected error:", str(e)[:120])
try: step("apply_material", objects="Nope", preset="gold")
except Exception as e: print("expected error:", str(e)[:160])
step("delete_objects", names="Ball"); print(step("undo")); print(len(step("scene_info")["objects"]), "objects after undo")
print("session:", b.session_dir, f"total {time.time()-t:.1f}s")
b.close()
