"""Exercise the less common paths: looks with bloom, glass, HDRI, text, isometric, assets, final render, export."""
import sys, time
from blender_studio.launcher import Blender
out = sys.argv[1]
b = Blender()
def step(cmd, **a):
    t0 = time.time()
    try:
        r = b.call(cmd, **a); print(f"OK   {cmd:15s} {time.time()-t0:5.1f}s {str(r)[:200]}"); return r
    except Exception as e:
        print(f"FAIL {cmd:15s} {str(e)[:400]}")

step("create_object", kind="text", name="Sign", text="OPEN", location=[0, 0, 0.5], scale=0.5)
step("create_object", kind="sphere", name="Orb", scale=0.2, location=[-0.9, -0.2, 0.2])
step("create_object", kind="monkey", name="Suzanne", scale=0.3, location=[0.95, -0.1, 0.3], rotation_deg=[0, 0, -20])
step("apply_material", objects="Sign", preset="neon_tube", color="#ff3fa0")
step("apply_material", objects="Orb", preset="glass")
step("apply_material", objects="Suzanne", preset="chrome")
step("add_polish", objects="Suzanne", bevel=0, subdivision=2)
step("add_backdrop", style="cyclorama", color="#16161d", roughness=0.35)
step("studio_lighting", style="neon", strength=0.6)
step("frame_camera", shot="front", elevation_deg=8, aspect="16:9")
step("set_look", preset="cinematic")
print(step("scene_check"))
r = step("render", quality="preview"); 
if r: __import__("shutil").copy(r["path"], out + "_neon.png")
print(step("search_assets", kind="hdri", query="studio", limit=5))
step("studio_lighting", style="hdri", hdri="studio_small_08")
step("set_look", preset="product_clean")
r = step("render", quality="final", samples=64)
if r: __import__("shutil").copy(r["path"], out + "_hdri_cycles.png")
print(step("search_assets", kind="texture", query="wood floor", limit=4))
print(step("search_assets", kind="model", query="chair", limit=4))
step("apply_texture", objects="Cyclorama", asset_id="wood_floor_deck")
step("import_asset", asset_id="ArmChair_01", fit_height=0.9, location=[0, 1.2, 0])
step("frame_camera", shot="isometric")
step("set_look", preset="flat_graphic")
step("studio_lighting", style="softbox")
r = step("render", quality="draft")
if r: __import__("shutil").copy(r["path"], out + "_iso.png")
step("export_model", path=out + "_scene.glb")
step("save_blend")
b.close()
