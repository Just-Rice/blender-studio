"""Exercise sculpting, characters, animation, physics and video. Usage: motion.py OUT_DIR"""
import shutil, sys, time
from pathlib import Path
from blender_studio.launcher import Blender
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
only = sys.argv[2].split(",") if len(sys.argv) > 2 else None
b = Blender(); fails = []
def step(cmd, **a):
    t0 = time.time()
    try:
        r = b.call(cmd, **a); print(f"OK   {cmd:18s} {time.time()-t0:5.1f}s {str(r)[:170]}", flush=True); return r
    except Exception as e:
        fails.append(cmd); print(f"FAIL {cmd:18s} {str(e)[:500]}", flush=True)
def shot(name, **a):
    r = step("render", quality="draft", **a)
    if r: shutil.copy(r["path"], out / f"{name}.png")
def want(name): return only is None or name in only

if want("sculpt"):
    step("new_scene")
    step("create_terrain", name="Ground", size=8, height=0.8, island=True, seed=3)
    step("create_rock", name="Boulder", size=1.2, roughness=0.4, seed=1, location=[-1.6, 0.4, 0.3])
    step("create_rock", name="Stone", size=0.6, style="lowpoly", seed=5, location=[1.9, -0.8, 0.25])
    step("create_blob", name="Cloud", balls=[[0, 0, 0, 0.5], [0.55, 0, 0.1, 0.4], [-0.5, 0.05, 0.05, 0.38], [0.1, 0, 0.35, 0.36]], location=[0, 1.2, 2.6])
    step("create_limbs", name="Tree", joints={"root": [0, 0, 0, 0.16], "mid": [0.05, 0, 0.8, 0.11], "fork": [0, 0, 1.3, 0.09], "a": [0.5, 0.1, 1.9, 0.04], "b": [-0.45, -0.1, 1.85, 0.04], "c": [0.05, 0.3, 2.1, 0.035]},
         links=[["root", "mid"], ["mid", "fork"], ["fork", "a"], ["fork", "b"], ["fork", "c"]], location=[0.4, 0.2, 0.45])
    step("create_object", kind="cube", name="Crate", scale=0.35, location=[1.0, 0.9, 0.75])
    step("create_object", kind="sphere", name="Bite", scale=0.3, location=[1.3, 0.6, 1.05])
    step("boolean", target="Crate", cutter="Bite")
    step("create_object", kind="sphere", name="Lump", scale=0.35, location=[-0.6, -1.4, 0.7])
    step("sculpt", objects="Lump", roughness=0.18, detail=1.5, smooth=1)
    step("apply_material", objects="Ground", preset="clay", color="#7fb85a")
    step("apply_material", objects=["Boulder", "Stone"], preset="stone")
    step("apply_material", objects="Cloud", preset="porcelain")
    step("apply_material", objects="Tree", preset="wood")
    step("apply_material", objects="Crate", preset="plastic_matte", color="#d98a3d")
    step("apply_material", objects="Lump", preset="clay", color="#c9695a")
    step("add_backdrop", style="floor", color="#3aa7c9")
    step("studio_lighting", style="golden_hour")
    step("frame_camera", shot="three_quarter", elevation_deg=22)
    step("set_look", preset="vivid")
    print(step("scene_check")); shot("sculpt")

if want("people"):
    step("new_scene")
    poses = ["stand", "wave", "cheer", "walk", "run", "sit", "point", "hands_on_hips", "think", "jump", "t_pose"]
    styles = ["toy", "lowpoly", "blocky"]
    for i, pose in enumerate(poses):
        step("create_character", name=f"P{i}", style=styles[i % 3], pose=pose, location=[(i - 5) * 1.15, 0, 0],
             top=["#3f7fd0", "#d6583b", "#4aa56b", "#e2b23a"][i % 4], height=1.7)
    step("add_backdrop", style="cyclorama", color="#e6e1d8")
    step("studio_lighting", style="softbox")
    step("frame_camera", shot="front", elevation_deg=8, aspect="21:9", fill=0.92)
    step("set_look", preset="product_clean")
    print(step("scene_check")); print(str(step("scene_info"))[:600]); shot("people")
    step("pose_character", character="P0", bones={"upper_arm.L": [0, 0, 120], "head": [0, 30, 0]})
    step("apply_material", objects="P0", preset="gold")
    step("frame_camera", shot="three_quarter", subjects=["P0", "P1", "P2"]); shot("people_close")
    step("contact_sheet", subjects="P1")

if want("motion"):
    step("new_scene")
    step("create_character", name="Hero", style="toy", location=[-1.5, 0, 0], facing_deg=90, top="#d6583b")
    step("create_object", kind="ico_sphere", name="Gem", scale=0.25, location=[1.6, 0, 1.2])
    step("apply_material", objects="Gem", preset="gold")
    step("add_backdrop", style="cyclorama", color="#2b3a55")
    step("studio_lighting", style="three_point")
    step("frame_camera", shot="front", elevation_deg=10, fill=0.7)
    step("set_look", preset="vivid")
    step("animate_character", character="Hero", clip="walk", seconds=2, distance=2.4)
    step("animate_character", character="Hero", clip="jump", seconds=1.3, start_seconds=2)
    step("animate", kind="float", target="Gem", seconds=3.3)
    step("animate", kind="spin", target="Gem", seconds=3.3)
    step("animate", kind="dolly", seconds=3.3, amount=0.2)
    print(step("set_time", seconds=1.0)); print(step("list_animations"))
    shot("motion_1s", at_seconds=1.0); shot("motion_2_6s", at_seconds=2.65)
    r = step("render_animation", quality="draft")
    if r: shutil.copy(r["path"], out / "motion.mp4"); print(r["stills"][0])

if want("physics"):
    step("new_scene")
    step("create_object", kind="cylinder", name="Table", scale=[0.5, 0.5, 0.35], location=[0, 0, 0.35])
    step("apply_material", objects="Table", preset="wood")
    step("add_backdrop", style="cyclorama", color="#d9d2c4")
    cols = ["#d6332b", "#3c6fd1", "#e2b23a", "#4aa56b", "#8a5fd1", "#e07a3a"]
    names = []
    for i in range(6):
        n = f"Block{i}"; names.append(n)
        step("create_object", kind=["cube", "sphere", "cylinder"][i % 3], name=n, scale=0.09,
             location=[(i % 3 - 1) * 0.16, (i // 3 - 0.5) * 0.2, 1.3 + i * 0.28], rotation_deg=[20 * i, 35, 10 * i])
        step("apply_material", objects=n, preset="plastic_glossy", color=cols[i])
    step("add_polish", objects=names, bevel=0.08)
    step("studio_lighting", style="softbox")
    step("frame_camera", shot="three_quarter", subjects="Table", fill=0.5)
    step("drop_objects", objects=names, seconds=2.5)
    print(step("scene_check")); shot("physics_end")
    r = step("render_animation", quality="draft", seconds=2.5)
    if r: shutil.copy(r["path"], out / "physics.mp4")
    step("clear_animation")
    step("drape_cloth", over="Table", color="#b04a5a", size=1.9)
    step("frame_camera", shot="three_quarter", fill=0.7); shot("cloth")
    step("animate", kind="turntable", seconds=3); step("animate", kind="light_fade", seconds=1)
    r = step("render_animation", quality="draft")
    if r: shutil.copy(r["path"], out / "turntable.mp4")
    step("undo", steps=2)

b.close()
print("FAILS:", fails or "none")
