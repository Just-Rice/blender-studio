"""Scene basics: inspect, create, move, delete, run Python, save, import and export."""
import contextlib
import io
import math
import os

import bmesh
import bpy
import mathutils

from .. import state, util
from ..commands import command

PRIMITIVES = ("cube", "sphere", "ico_sphere", "cylinder", "cone", "torus", "plane", "monkey", "text")


@command()
def new_scene():
    """Empty the scene and reset to sensible render defaults."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)
    for store in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                  bpy.data.curves, bpy.data.images, bpy.data.node_groups):
        for block in list(store):
            if block.users == 0:
                store.remove(block)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    scene.render.resolution_percentage = 100
    scene.unit_settings.system = "METRIC"
    return {"ok": "Scene is empty. Units are metres, Z is up, -Y is the front."}


def _describe(obj):
    info = {
        "name": obj.name,
        "type": obj.type,
        "location": util.rounded(obj.location),
        "size": util.rounded(obj.dimensions),
    }
    if any(abs(a) > 1e-4 for a in obj.rotation_euler):
        info["rotation_deg"] = [round(math.degrees(a), 1) for a in obj.rotation_euler]
    if obj.type == "MESH":
        info["materials"] = [s.material.name if s.material else None for s in obj.material_slots]
        info["faces"] = len(obj.data.polygons)
    if obj.modifiers:
        info["modifiers"] = [m.type for m in obj.modifiers]
    if obj.parent:
        info["parent"] = obj.parent.name
    if obj.type == "LIGHT":
        info["light"] = {"kind": obj.data.type, "power": round(obj.data.energy, 1)}
    return info


@command(mutates=False)
def scene_info():
    scene = bpy.context.scene
    subjects = util.subjects()
    helpers = [o for o in scene.objects if util.is_helper(o)]
    others = [o for o in scene.objects if o not in subjects and not util.is_helper(o)]
    info = {
        "objects": [_describe(o) for o in subjects[:80]],
        "object_count": len(subjects),
        "studio_equipment": [f"{o.name} ({o.type.lower()})" for o in helpers],
        "other": [_describe(o) for o in others[:20]],
        "active_camera": scene.camera.name if scene.camera else None,
        "render": {
            "engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "look": scene.view_settings.look,
        },
    }
    if subjects:
        lo, hi, center, radius = util.bounds(subjects)
        info["bounds"] = {"min": util.rounded(lo), "max": util.rounded(hi),
                          "center": util.rounded(center), "radius": round(radius, 3)}
    return info


def _apply_transform(obj, location, rotation_deg, scale):
    if location is not None:
        obj.location = location
    if rotation_deg is not None:
        obj.rotation_euler = [math.radians(a) for a in rotation_deg]
    if scale is not None:
        obj.scale = [scale] * 3 if isinstance(scale, (int, float)) else scale


@command()
def create_object(kind, name=None, location=None, rotation_deg=None, scale=None, text=None):
    kind = kind.lower()
    if kind not in PRIMITIVES:
        raise ValueError(f"Unknown kind '{kind}'. Choose from: {', '.join(PRIMITIVES)}")
    if kind == "text":
        curve = bpy.data.curves.new(name or "Text", "FONT")
        curve.body = text or "Text"
        curve.align_x, curve.align_y = "CENTER", "CENTER"
        curve.extrude, curve.bevel_depth, curve.bevel_resolution = 0.06, 0.012, 3
        obj = bpy.data.objects.new(name or "Text", curve)
        obj.rotation_euler.x = math.radians(90)
    else:
        mesh = bpy.data.meshes.new(name or kind.title())
        bm = bmesh.new()
        if kind == "cube":
            bmesh.ops.create_cube(bm, size=2.0)
        elif kind == "sphere":
            bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0)
        elif kind == "ico_sphere":
            bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        elif kind == "cylinder":
            bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=1.0, radius2=1.0, depth=2.0)
        elif kind == "cone":
            bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=1.0, radius2=0.0, depth=2.0)
        elif kind == "torus":
            bm.free()
            bm = _torus(1.0, 0.3, 64, 24)
        elif kind == "plane":
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)
        elif kind == "monkey":
            bmesh.ops.create_monkey(bm)
        smooth = kind in ("sphere", "cylinder", "cone", "torus", "monkey")
        for face in bm.faces:
            # Keep flat caps flat; only the curved sides get smooth shading.
            face.smooth = smooth and not (kind in ("cylinder", "cone") and len(face.verts) > 4)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name or kind.title(), mesh)
    bpy.context.scene.collection.objects.link(obj)
    _apply_transform(obj, location, rotation_deg, scale)
    bpy.context.view_layer.update()
    return _describe(obj)


def _torus(major, minor, major_seg, minor_seg):
    bm = bmesh.new()
    rings = []
    for i in range(major_seg):
        a = 2 * math.pi * i / major_seg
        ring = []
        for j in range(minor_seg):
            b = 2 * math.pi * j / minor_seg
            r = major + minor * math.cos(b)
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), minor * math.sin(b))))
        rings.append(ring)
    for i in range(major_seg):
        for j in range(minor_seg):
            ni, nj = (i + 1) % major_seg, (j + 1) % minor_seg
            bm.faces.new((rings[i][j], rings[ni][j], rings[ni][nj], rings[i][nj]))
    return bm


@command()
def transform_object(name, location=None, rotation_deg=None, scale=None):
    obj = util.get_object(name)
    _apply_transform(obj, location, rotation_deg, scale)
    bpy.context.view_layer.update()
    return _describe(obj)


@command()
def delete_objects(names):
    removed = []
    for name in util.as_list(names):
        obj = util.get_object(name)
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": removed}


@command()
def run_python(code):
    """Escape hatch for custom modelling. Set a variable named `result` to return a value."""
    namespace = {"bpy": bpy, "bmesh": bmesh, "mathutils": mathutils, "math": math,
                 "Vector": mathutils.Vector, "util": util}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(compile(code, "<run_python>", "exec"), namespace)
    bpy.context.view_layer.update()
    out = {"output": stdout.getvalue()[-4000:]}
    if "result" in namespace:
        out["result"] = namespace["result"]
    return out


@command(mutates=False)
def save_blend(path=None):
    path = os.path.abspath(os.path.expanduser(path)) if path else os.path.join(state.session_dir, "scene.blend")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, check_existing=False)
    return {"saved": path}


@command(mutates=False)
def export_model(path, include_studio=False):
    """Export to .glb, .gltf, .obj, .stl, .fbx or .usdc; studio lights and backdrop are left out."""
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    for obj in bpy.context.scene.objects:
        obj.select_set(include_studio or not util.is_helper(obj))
    if ext in (".glb", ".gltf"):
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_apply=True,
                                  export_format="GLB" if ext == ".glb" else "GLTF_SEPARATE")
    elif ext == ".obj":
        bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, apply_modifiers=True)
    elif ext == ".stl":
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True)
    elif ext == ".fbx":
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True)
    elif ext in (".usd", ".usdc", ".usda"):
        bpy.ops.wm.usd_export(filepath=path, selected_objects_only=True)
    else:
        raise ValueError(f"Unsupported export type '{ext}'. Use .glb, .gltf, .obj, .stl, .fbx or .usdc.")
    return {"exported": path, "bytes": os.path.getsize(path)}


@command()
def import_model(path, name=None, fit_height=None):
    """Import a model file. fit_height rescales it so it stands that many metres tall."""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        raise ValueError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext in (".usd", ".usdc", ".usda", ".usdz"):
        bpy.ops.wm.usd_import(filepath=path)
    else:
        raise ValueError(f"Unsupported import type '{ext}'.")
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent not in new]
    for obj in new:
        # Importers drop objects into whichever collection is active; keep them out of the studio's own.
        if util.is_helper(obj):
            for col in list(obj.users_collection):
                col.objects.unlink(obj)
            bpy.context.scene.collection.objects.link(obj)
    if fit_height and new:
        lo, hi, _, _ = util.bounds([o for o in new if o.type in util.RENDERABLE] or new)
        factor = fit_height / max(hi.z - lo.z, 1e-6)
        for root in roots:
            root.scale *= factor
            root.location *= factor
        lo, _, _, _ = util.bounds([o for o in new if o.type in util.RENDERABLE] or new)
        for root in roots:
            root.location.z -= lo.z
    if name and len(roots) == 1:
        roots[0].name = name
    return {"imported": [o.name for o in new][:60], "roots": [o.name for o in roots]}
