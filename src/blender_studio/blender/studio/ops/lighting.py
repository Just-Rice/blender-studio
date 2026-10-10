"""Lighting rigs and backdrops, sized automatically to whatever is in the scene."""
import math

import bmesh
import bpy
from mathutils import Vector

from .. import util
from ..commands import command

STYLES = {
    "three_point": "Classic key, fill and rim. Safe default for any single subject.",
    "softbox": "Big soft overhead light with side strips. Clean product-shot look.",
    "golden_hour": "Low warm sun with a real sky. Outdoor, long soft shadows.",
    "overcast": "Even, shadowless daylight. Good for showing form and colour honestly.",
    "dramatic": "One hard side light and a thin rim against darkness. Moody, high contrast.",
    "neon": "Magenta and cyan coloured lights in a dark room. Stylised, synthwave.",
    "hdri": "Real-world photo lighting from Poly Haven (pass hdri=<id>). Most realistic reflections.",
}
BACKDROPS = ("cyclorama", "floor", "none")


def _world():
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Studio World")
    util.enable_nodes(scene.world)
    tree = scene.world.node_tree
    tree.nodes.clear()
    return tree


def world_color(color, strength=1.0):
    tree = _world()
    background = tree.nodes.new("ShaderNodeBackground")
    output = tree.nodes.new("ShaderNodeOutputWorld")
    background.inputs[0].default_value = util.rgba(color)
    background.inputs[1].default_value = strength
    tree.links.new(background.outputs[0], output.inputs[0])


def world_sky(elevation_deg, rotation_deg, strength):
    tree = _world()
    sky = tree.nodes.new("ShaderNodeTexSky")
    for model in ("MULTIPLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
        if util.set_if(sky, "sky_type", model):
            break
    util.set_if(sky, "sun_elevation", math.radians(elevation_deg))
    util.set_if(sky, "sun_rotation", math.radians(rotation_deg))
    util.set_if(sky, "sun_disc", False)
    # The sky model is black below the horizon; mirror it so downward-looking cameras see haze, not a void.
    coords = tree.nodes.new("ShaderNodeTexCoord")
    split = tree.nodes.new("ShaderNodeSeparateXYZ")
    absolute = tree.nodes.new("ShaderNodeMath")
    absolute.operation = "ABSOLUTE"
    join = tree.nodes.new("ShaderNodeCombineXYZ")
    tree.links.new(coords.outputs["Generated"], split.inputs[0])
    tree.links.new(split.outputs[0], join.inputs[0])
    tree.links.new(split.outputs[1], join.inputs[1])
    tree.links.new(split.outputs[2], absolute.inputs[0])
    tree.links.new(absolute.outputs[0], join.inputs[2])
    tree.links.new(join.outputs[0], sky.inputs[0])
    background = tree.nodes.new("ShaderNodeBackground")
    output = tree.nodes.new("ShaderNodeOutputWorld")
    background.inputs[1].default_value = strength
    tree.links.new(sky.outputs[0], background.inputs[0])
    tree.links.new(background.outputs[0], output.inputs[0])


def world_hdri(path, strength=1.0, rotation_deg=0.0):
    tree = _world()
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    env = tree.nodes.new("ShaderNodeTexEnvironment")
    background = tree.nodes.new("ShaderNodeBackground")
    output = tree.nodes.new("ShaderNodeOutputWorld")
    env.image = bpy.data.images.load(path, check_existing=True)
    mapping.inputs["Rotation"].default_value[2] = math.radians(rotation_deg)
    background.inputs[1].default_value = strength
    tree.links.new(coords.outputs["Generated"], mapping.inputs[0])
    tree.links.new(mapping.outputs[0], env.inputs[0])
    tree.links.new(env.outputs[0], background.inputs[0])
    tree.links.new(background.outputs[0], output.inputs[0])


def _aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def _light(name, kind, center, radius, azimuth, elevation, distance, power, color=(1, 1, 1), size=1.0, spot_deg=45):
    """Place a light on a sphere around the subject. Azimuth 0 is the front (-Y), 90 is the right (+X)."""
    data = bpy.data.lights.new(name, kind)
    data.color = color
    az, el = math.radians(azimuth), math.radians(elevation)
    d = distance * radius
    obj = bpy.data.objects.new(name, data)
    obj.location = center + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * d
    if kind == "SUN":
        data.energy = power
        data.angle = math.radians(size)
    else:
        # Power grows with distance squared so exposure stays the same at any scene scale.
        data.energy = power * radius * radius
        if kind == "AREA":
            data.shape = "DISK"
            data.size = size * radius
        else:
            data.shadow_soft_size = size * radius
        if kind == "SPOT":
            data.spot_size = math.radians(spot_deg)
            data.spot_blend = 0.4
    util.link_only(obj, util.LIGHTS)
    _aim(obj, center)
    return obj


def _rig(style, center, radius, s):
    """Build the lights for a style. s is the overall strength multiplier."""
    L = lambda *a, **k: _light(*a[:2], center, radius, *a[2:], **k)
    if style == "three_point":
        world_color((0.05, 0.055, 0.065), 1.0)
        L("Key", "AREA", 40, 38, 3.2, 380 * s, color=(1.0, 0.95, 0.88), size=1.6)
        L("Fill", "AREA", -55, 15, 3.4, 95 * s, color=(0.85, 0.92, 1.0), size=3.0)
        L("Rim", "AREA", 160, 40, 3.2, 440 * s, color=(1.0, 0.98, 0.95), size=1.2)
    elif style == "softbox":
        world_color((0.72, 0.74, 0.78), 0.25 * s)
        L("Top Softbox", "AREA", 10, 78, 3.0, 400 * s, size=4.0)
        L("Left Strip", "AREA", -75, 18, 3.4, 140 * s, color=(0.94, 0.97, 1.0), size=2.4)
        L("Right Strip", "AREA", 70, 22, 3.4, 190 * s, color=(1.0, 0.97, 0.93), size=2.4)
    elif style == "golden_hour":
        world_sky(elevation_deg=9, rotation_deg=50, strength=0.2 * s)
        L("Sun", "SUN", -52, 14, 6, 8.0 * s, color=(1.0, 0.62, 0.32), size=2.5)
        L("Sky Fill", "AREA", 100, 50, 3.6, 50 * s, color=(0.62, 0.76, 1.0), size=4.0)
    elif style == "overcast":
        world_color((0.82, 0.86, 0.92), 1.15 * s)
        L("Sky Glow", "AREA", 20, 80, 3.4, 420 * s, color=(0.95, 0.97, 1.0), size=5.0)
    elif style == "dramatic":
        world_color((0.004, 0.004, 0.006), 1.0)
        L("Key", "SPOT", 72, 32, 3.4, 800 * s, color=(1.0, 0.9, 0.78), size=0.12, spot_deg=42)
        L("Rim", "AREA", -150, 30, 3.2, 260 * s, color=(0.6, 0.75, 1.0), size=0.8)
    elif style == "neon":
        world_color((0.006, 0.004, 0.014), 1.0)
        L("Magenta", "AREA", -65, 22, 3.0, 420 * s, color=(1.0, 0.08, 0.55), size=2.0)
        L("Cyan", "AREA", 70, 28, 3.0, 420 * s, color=(0.05, 0.75, 1.0), size=2.0)
        L("Violet Rim", "AREA", 175, 45, 3.0, 300 * s, color=(0.45, 0.2, 1.0), size=1.2)


def _reflection_probe(hi, center, radius):
    """EEVEE only reflects what is on screen; this captures the surroundings for everything else,
    so glossy objects do not show a seam where the off-screen floor should be."""
    try:
        data = bpy.data.lightprobes.new("Reflections", "SPHERE")
    except (TypeError, AttributeError):
        return
    data.influence_distance = radius * 6
    data.clip_start, data.clip_end = radius * 0.05, radius * 200
    obj = bpy.data.objects.new("Reflections", data)
    obj.location = (center.x, center.y, hi.z + radius * 0.4)
    util.link_only(obj, util.LIGHTS)


@command()
def studio_lighting(style="three_point", strength=1.0, subjects=None, hdri=None, hdri_rotation_deg=0.0):
    style = style.lower()
    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Choose from: {', '.join(STYLES)}")
    _, hi, center, radius = util.bounds(util.require_subjects(subjects))
    util.clear_collection(util.LIGHTS)
    _reflection_probe(hi, center, radius)
    notes = []
    if style == "hdri":
        from .assets import fetch_hdri
        hdri = hdri or "studio_small_08"
        world_hdri(fetch_hdri(hdri), strength, hdri_rotation_deg)
        _light("Kicker", "AREA", center, radius, 150, 40, 3.2, 350 * strength, size=1.2)
        notes.append(f"Lit by Poly Haven HDRI '{hdri}'.")
    else:
        _rig(style, center, radius, strength)
    lights = [o.name for o in util.ensure_collection(util.LIGHTS).objects if o.type == "LIGHT"]
    return {"style": style, "lights": lights, "aimed_at": util.rounded(center), "notes": notes,
            "tip": "Call render_preview to see the result; adjust strength if it is too dark or blown out."}


def _cyclorama(lo, center, radius):
    """Seamless curved backdrop: floor sweeping up into a wall behind the subject (+Y)."""
    half_width, front, back, curve, height = 22 * radius, 20 * radius, 5 * radius, 3 * radius, 16 * radius
    profile = [(-front, 0.0), (back, 0.0)]
    for i in range(1, 17):
        a = (math.pi / 2) * i / 16
        profile.append((back + curve * math.sin(a), curve * (1 - math.cos(a))))
    profile.append((back + curve, height))
    bm = bmesh.new()
    left = [bm.verts.new((-half_width, y, z)) for y, z in profile]
    right = [bm.verts.new((half_width, y, z)) for y, z in profile]
    for i in range(len(profile) - 1):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1])).smooth = True
    mesh = bpy.data.meshes.new("Cyclorama")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Cyclorama", mesh)
    obj.location = (center.x, center.y, lo.z)
    return obj


def _floor(lo, center, radius):
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=40 * radius)
    mesh = bpy.data.meshes.new("Floor")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Floor", mesh)
    obj.location = (center.x, center.y, lo.z)
    return obj


@command()
def add_backdrop(style="cyclorama", color="#d9d9de", roughness=0.6, subjects=None):
    """Give the subject something to stand on and cast shadows onto."""
    style = style.lower()
    if style not in BACKDROPS:
        raise ValueError(f"Unknown backdrop '{style}'. Choose from: {', '.join(BACKDROPS)}")
    lo, _, center, radius = util.bounds(util.require_subjects(subjects))
    util.clear_collection(util.BACKDROP)
    if style == "none":
        return {"backdrop": "removed"}
    obj = _cyclorama(lo, center, radius) if style == "cyclorama" else _floor(lo, center, radius)
    material = bpy.data.materials.new("Backdrop")
    util.enable_nodes(material)
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = util.rgba(color)
    shader.inputs["Roughness"].default_value = roughness
    obj.data.materials.append(material)
    util.link_only(obj, util.BACKDROP)
    return {"backdrop": style, "floor_height": round(lo.z, 3),
            "tip": "The curved wall is behind the subject (+Y); keep camera azimuth within about 60 degrees of front."}
