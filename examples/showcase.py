"""Three example scenes built only with Blender Studio commands. Usage: showcase.py OUT_DIR [quality]"""
import shutil
import sys
from pathlib import Path

from blender_studio.launcher import Blender

out = Path(sys.argv[1])
quality = sys.argv[2] if len(sys.argv) > 2 else "preview"
only = sys.argv[3].split(",") if len(sys.argv) > 3 else ["mug", "island", "neon"]
out.mkdir(parents=True, exist_ok=True)
b = Blender()


def shoot(name):
    print(name, b.call("scene_check"))
    shutil.copy(b.call("render", quality=quality)["path"], out / f"{name}.png")


def mug():
    b.call("new_scene")
    b.call("run_python", code="""
def cup(name, radius, height, wall):
    mesh = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=96, radius1=radius * 0.92, radius2=radius, depth=height)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z > 0.9], context='FACES')
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh); bpy.context.scene.collection.objects.link(obj)
    obj.location.z = height / 2
    mod = obj.modifiers.new('Wall', 'SOLIDIFY'); mod.thickness = wall; mod.offset = -1
    return obj
cup('Mug', 0.042, 0.095, 0.004)
""")
    b.call("create_object", kind="torus", name="Handle", scale=[0.03, 0.03, 0.036], location=[0.05, 0, 0.05],
           rotation_deg=[90, 0, 0])
    b.call("create_object", kind="cylinder", name="Coffee", scale=[0.037, 0.037, 0.002], location=[0, 0, 0.082])
    b.call("create_object", kind="cylinder", name="Saucer", scale=[0.075, 0.075, 0.004], location=[0, 0, 0.004])
    b.call("transform_object", name="Mug", location=[0, 0, 0.0555])
    b.call("transform_object", name="Handle", location=[0.05, 0, 0.058])
    b.call("transform_object", name="Coffee", location=[0, 0, 0.09])
    b.call("create_object", kind="sphere", name="Sugar", scale=0.008, location=[-0.1, -0.05, 0.008])
    b.call("create_object", kind="cube", name="Cube", scale=0.009, location=[-0.085, -0.075, 0.009],
           rotation_deg=[0, 0, 30])
    b.call("apply_material", objects=["Mug", "Handle", "Saucer"], preset="ceramic", color="#e9e2d5")
    b.call("apply_material", objects="Coffee", preset="plastic_glossy", color="#2a1408", roughness=0.03)
    b.call("apply_material", objects="Sugar", preset="gold")
    b.call("apply_material", objects="Cube", preset="porcelain")
    b.call("add_polish", objects=["Mug", "Saucer", "Cube"], bevel=0.05)
    b.call("add_backdrop", style="cyclorama", color="#c7694a", roughness=0.7)
    b.call("studio_lighting", style="softbox", strength=0.85)
    b.call("frame_camera", shot="three_quarter", subjects=["Mug", "Handle", "Saucer"], elevation_deg=24,
           fill=0.6, depth_of_field=4, aspect="4:3")
    b.call("set_look", preset="product_clean")
    shoot("mug")


def island():
    b.call("new_scene")
    b.call("run_python", code="""
import random
random.seed(7)
def solid(name, segments, r1, r2, depth, loc, jitter=0.0):
    mesh = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=r1, radius2=r2, depth=depth)
    for v in bm.verts:
        v.co.x += random.uniform(-jitter, jitter); v.co.y += random.uniform(-jitter, jitter)
    bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh); bpy.context.scene.collection.objects.link(obj)
    obj.location = loc; obj.rotation_euler.z = random.uniform(0, 6.28)
    return obj
solid('Rock', 9, 1.4, 2.6, 1.2, (0, 0, -0.6), 0.18)
solid('Grass', 9, 2.65, 2.5, 0.22, (0, 0, 0.11), 0.1)
spots = [(-1.3, 0.6, 1.0), (-0.6, 1.4, 0.75), (-1.5, -0.6, 0.8), (1.3, 1.1, 0.9), (0.4, -1.5, 0.7), (1.6, -0.5, 0.6)]
for i, (x, y, s) in enumerate(spots):
    solid(f'Trunk{i}', 6, 0.09 * s, 0.07 * s, 0.5 * s, (x, y, 0.22 + 0.25 * s))
    for j in range(3):
        solid(f'Leaves{i}_{j}', 7, (0.55 - j * 0.12) * s, 0.0, 0.7 * s, (x, y, 0.22 + (0.75 + j * 0.38) * s), 0.03)
""")
    b.call("create_object", kind="cube", name="House", scale=[0.45, 0.38, 0.32], location=[0.25, 0.1, 0.54])
    b.call("run_python", code="""
mesh = bpy.data.meshes.new('Roof'); bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=0.78, radius2=0.0, depth=0.5)
bm.to_mesh(mesh); bm.free()
roof = bpy.data.objects.new('Roof', mesh); bpy.context.scene.collection.objects.link(roof)
roof.location = (0.25, 0.1, 1.11); roof.rotation_euler.z = math.radians(45); roof.scale = (1.0, 0.86, 1.0)
""")
    b.call("create_object", kind="cube", name="Door", scale=[0.09, 0.02, 0.17], location=[0.25, -0.29, 0.39])
    b.call("create_object", kind="cube", name="Window", scale=[0.09, 0.02, 0.09], location=[0.53, -0.29, 0.62])
    info = b.call("scene_info")
    names = [o["name"] for o in info["objects"]]
    pick = lambda prefix: [n for n in names if n.startswith(prefix)]
    b.call("apply_material", objects="Rock", preset="clay", color="#8a7a6b")
    b.call("apply_material", objects="Grass", preset="clay", color="#7fb85a")
    b.call("apply_material", objects=pick("Trunk"), preset="clay", color="#7a4f30")
    b.call("apply_material", objects=pick("Leaves"), preset="clay", color="#3f8f5a")
    b.call("apply_material", objects="House", preset="clay", color="#f3e6cf")
    b.call("apply_material", objects="Roof", preset="clay", color="#d9573f")
    b.call("apply_material", objects="Door", preset="clay", color="#6b4a33")
    b.call("apply_material", objects="Window", preset="glow", color="#ffd98a", emission_strength=3)
    b.call("add_polish", objects=["House", "Door", "Window"], bevel=0.06, smooth=False)
    b.call("add_backdrop", style="floor", color="#3aa7c9", roughness=0.15)
    b.call("studio_lighting", style="golden_hour")
    b.call("frame_camera", shot="isometric", subjects=["Rock", "Grass", "House", "Roof"] + pick("Leaves"),
           fill=0.82, aspect="1:1")
    b.call("set_look", preset="vivid", bloom=0.1)
    shoot("island")


def neon():
    b.call("new_scene")
    b.call("create_object", kind="text", name="Sign", text="HELLO", location=[0, 0, 0.43], scale=0.6)
    b.call("run_python", code="""
sign = bpy.data.objects['Sign']
sign.data.extrude = 0.0; sign.data.bevel_depth = 0.035; sign.data.bevel_resolution = 6; sign.data.fill_mode = 'NONE'
""")
    b.call("create_object", kind="sphere", name="Orb", scale=0.22, location=[-1.15, -0.55, 0.22])
    b.call("create_object", kind="torus", name="Ring", scale=0.3, location=[1.2, -0.5, 0.385], rotation_deg=[70, 0, 25])
    b.call("create_object", kind="cube", name="Plinth", scale=[1.25, 0.18, 0.1], location=[0, 0.05, 0.1])
    b.call("apply_material", objects="Sign", preset="neon_tube", color="#ff3fa0")
    b.call("apply_material", objects="Orb", preset="chrome")
    b.call("apply_material", objects="Ring", preset="neon_tube", color="#30d5ff", emission_strength=9)
    b.call("apply_material", objects="Plinth", preset="plastic_matte", color="#15151c")
    b.call("add_polish", objects="Plinth", bevel=0.12)
    b.call("add_backdrop", style="cyclorama", color="#101018", roughness=0.28)
    b.call("studio_lighting", style="neon", strength=0.45)
    b.call("frame_camera", shot="front", azimuth_deg=-14, elevation_deg=7, focal_length=50, fill=0.72, aspect="16:9")
    b.call("set_look", preset="cinematic", bloom=0.5)
    shoot("neon")


for name in only:
    {"mug": mug, "island": island, "neon": neon}[name]()
b.close()
