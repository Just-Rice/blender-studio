"""Shared helpers: finding objects, measuring them, and managing the studio's helper collections."""
import warnings

import bpy
from mathutils import Vector

LIGHTS = "Studio Lights"
BACKDROP = "Studio Backdrop"
CAMERAS = "Studio Cameras"
HELPER_COLLECTIONS = (LIGHTS, BACKDROP, CAMERAS)
RENDERABLE = {"MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME", "POINTCLOUD", "CURVES"}


def ensure_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def clear_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        return
    for obj in list(col.objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.batch_remove([data])


def link_only(obj, collection_name):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    ensure_collection(collection_name).objects.link(obj)


def is_helper(obj):
    return any(col.name in HELPER_COLLECTIONS for col in obj.users_collection)


def as_list(value):
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def get_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        names = ", ".join(sorted(o.name for o in bpy.data.objects)[:40]) or "(scene is empty)"
        raise ValueError(f"No object named '{name}'. Objects in scene: {names}")
    return obj


def subjects(names=None):
    """The things being photographed: named objects, or everything that is not studio equipment."""
    if names:
        return [get_object(n) for n in as_list(names)]
    return [
        o for o in bpy.context.scene.objects
        if o.type in RENDERABLE and not is_helper(o) and not o.hide_render
    ]


def require_subjects(names=None):
    found = subjects(names)
    if not found:
        raise ValueError("The scene has no objects yet. Create or import something first.")
    return found


def bounds(objs):
    """World-space bounding box of objs as (min, max, center, radius)."""
    bpy.context.view_layer.update()
    lo = Vector((float("inf"),) * 3)
    hi = Vector((float("-inf"),) * 3)
    for obj in objs:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, world))
            hi = Vector(map(max, hi, world))
    if lo.x == float("inf"):
        lo, hi = Vector((-1, -1, 0)), Vector((1, 1, 2))
    center = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 1e-4)
    return lo, hi, center, radius


def bbox_corners(objs):
    bpy.context.view_layer.update()
    return [obj.matrix_world @ Vector(c) for obj in objs for c in obj.bound_box]


def enable_nodes(datablock):
    # use_nodes is always on from Blender 5 and slated for removal in 6.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            datablock.use_nodes = True
        except AttributeError:
            pass


def set_if(target, attr, value):
    """Set an attribute that only exists in some Blender versions."""
    if hasattr(target, attr):
        try:
            setattr(target, attr, value)
            return True
        except (TypeError, ValueError, AttributeError):
            return False
    return False


def rgba(color, default=(0.8, 0.8, 0.8, 1.0)):
    """Accept '#rrggbb' or [r, g, b] (0-1, sRGB as picked on screen) and return linear RGBA."""
    if color is None:
        return tuple(default)
    if isinstance(color, str):
        text = color.lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) != 6:
            raise ValueError(f"Colour '{color}' should look like '#ff8800'.")
        channels = [int(text[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    else:
        channels = [float(c) for c in color][:3]
        if len(channels) != 3:
            raise ValueError("Colour should be '#rrggbb' or three numbers between 0 and 1.")
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return (*linear, 1.0)


def rounded(vec, digits=3):
    return [round(float(v), digits) for v in vec]
