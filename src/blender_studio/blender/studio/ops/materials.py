"""Material presets built on the Principled shader, with a few procedural surfaces."""
import bpy

from .. import util
from ..commands import command

# Each preset: default colour, Principled inputs, and an optional procedural detail pass.
PRESETS = {
    "plastic_glossy": dict(color="#d6332b", inputs={"Roughness": 0.18, "Coat Weight": 0.4, "Coat Roughness": 0.05}),
    "plastic_matte": dict(color="#3c6fd1", inputs={"Roughness": 0.55}),
    "rubber": dict(color="#1c1c1e", inputs={"Roughness": 0.85, "Specular IOR Level": 0.3}, detail="fine_bump"),
    "clay": dict(color="#c9b8a6", inputs={"Roughness": 0.9, "Sheen Weight": 0.25, "Sheen Roughness": 0.6}),
    "ceramic": dict(color="#f2efe9", inputs={"Roughness": 0.28, "Coat Weight": 1.0, "Coat Roughness": 0.03}),
    "porcelain": dict(color="#fbfaf7", inputs={"Roughness": 0.2, "Coat Weight": 1.0, "Coat Roughness": 0.02,
                                               "Subsurface Weight": 0.25, "Subsurface Scale": 0.02}),
    "steel": dict(color="#b9bcc0", inputs={"Metallic": 1.0, "Roughness": 0.32}, detail="brushed"),
    "chrome": dict(color="#f0f0f0", inputs={"Metallic": 1.0, "Roughness": 0.04}),
    "gold": dict(color="#ffc35c", inputs={"Metallic": 1.0, "Roughness": 0.16}),
    "copper": dict(color="#f0a17e", inputs={"Metallic": 1.0, "Roughness": 0.22}),
    "aluminium": dict(color="#dfe1e3", inputs={"Metallic": 1.0, "Roughness": 0.42}, detail="fine_bump"),
    "car_paint": dict(color="#b3121c", inputs={"Metallic": 0.7, "Roughness": 0.35, "Coat Weight": 1.0,
                                               "Coat Roughness": 0.02}),
    "glass": dict(color="#ffffff", inputs={"Transmission Weight": 1.0, "Roughness": 0.0, "IOR": 1.5}, glass=True),
    "frosted_glass": dict(color="#f4f8fa", inputs={"Transmission Weight": 1.0, "Roughness": 0.32, "IOR": 1.5},
                          glass=True),
    "water": dict(color="#dff3f7", inputs={"Transmission Weight": 1.0, "Roughness": 0.02, "IOR": 1.33}, glass=True),
    "wood": dict(color="#9a6236", inputs={"Roughness": 0.5, "Coat Weight": 0.2, "Coat Roughness": 0.2},
                 detail="wood"),
    "fabric": dict(color="#55688a", inputs={"Roughness": 0.92, "Sheen Weight": 0.8, "Sheen Roughness": 0.45},
                   detail="weave"),
    "velvet": dict(color="#6a1230", inputs={"Roughness": 1.0, "Sheen Weight": 1.0, "Sheen Roughness": 0.3}),
    "concrete": dict(color="#8d8d8a", inputs={"Roughness": 0.88}, detail="rough"),
    "stone": dict(color="#77736c", inputs={"Roughness": 0.75}, detail="rough"),
    "skin": dict(color="#d9a183", inputs={"Roughness": 0.45, "Subsurface Weight": 0.6, "Subsurface Scale": 0.05}),
    "wax": dict(color="#f1e3c0", inputs={"Roughness": 0.4, "Subsurface Weight": 1.0, "Subsurface Scale": 0.1}),
    "glow": dict(color="#ff5a1f", inputs={"Roughness": 0.4, "Emission Strength": 5.0}, emissive=True),
    "neon_tube": dict(color="#22e0ff", inputs={"Roughness": 0.2, "Emission Strength": 12.0}, emissive=True),
}


def _set_inputs(shader, values):
    skipped = []
    for key, value in values.items():
        socket = shader.inputs.get(key)
        if socket is None:
            skipped.append(key)
        else:
            socket.default_value = value
    return skipped


def _object_coords(tree, scale):
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = scale
    tree.links.new(coords.outputs["Object"], mapping.inputs[0])
    return mapping.outputs[0]


def _bump(tree, shader, height_socket, strength, distance=0.01):
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    tree.links.new(height_socket, bump.inputs["Height"])
    tree.links.new(bump.outputs[0], shader.inputs["Normal"])


def _noise(tree, vector, scale, detail=6.0, roughness=0.6):
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = detail
    noise.inputs["Roughness"].default_value = roughness
    tree.links.new(vector, noise.inputs["Vector"])
    return noise.outputs[0]


def _detail(kind, tree, shader, base, size, local_size):
    """Procedural surface detail, scaled to the object. Patterns live in the object's own (unscaled)
    coordinates, so their density uses local_size; bump depth is a real distance and uses size."""
    k = 1.0 / max(local_size, 1e-4)
    if kind == "fine_bump":
        _bump(tree, shader, _noise(tree, _object_coords(tree, (1, 1, 1)), 260 * k), 0.12, 0.002 * size)
    elif kind == "brushed":
        streaks = _noise(tree, _object_coords(tree, (1, 1, 90)), 30 * k, detail=3.0)
        _bump(tree, shader, streaks, 0.08, 0.002 * size)
    elif kind == "rough":
        coords = _object_coords(tree, (1, 1, 1))
        large = _noise(tree, coords, 9 * k, detail=10.0, roughness=0.7)
        ramp = tree.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = [c * 0.62 for c in base[:3]] + [1]
        ramp.color_ramp.elements[1].color = [min(c * 1.25, 1) for c in base[:3]] + [1]
        tree.links.new(large, ramp.inputs[0])
        tree.links.new(ramp.outputs[0], shader.inputs["Base Color"])
        _bump(tree, shader, _noise(tree, coords, 55 * k, detail=12.0, roughness=0.75), 0.35, 0.02 * size)
    elif kind == "weave":
        coords = _object_coords(tree, (1, 1, 1))
        wave_a = tree.nodes.new("ShaderNodeTexWave")
        wave_b = tree.nodes.new("ShaderNodeTexWave")
        wave_b.bands_direction = "Y"
        mix = tree.nodes.new("ShaderNodeMath")
        mix.operation = "MAXIMUM"
        for wave in (wave_a, wave_b):
            wave.inputs["Scale"].default_value = 140 * k
            tree.links.new(coords, wave.inputs["Vector"])
        tree.links.new(wave_a.outputs[1], mix.inputs[0])
        tree.links.new(wave_b.outputs[1], mix.inputs[1])
        _bump(tree, shader, mix.outputs[0], 0.5, 0.004 * size)
    elif kind == "wood":
        coords = _object_coords(tree, (1, 1, 0.12))
        rings = tree.nodes.new("ShaderNodeTexWave")
        rings.wave_type = "RINGS"
        rings.inputs["Scale"].default_value = 5.5 * k
        rings.inputs["Distortion"].default_value = 3.5
        rings.inputs["Detail"].default_value = 3.0
        rings.inputs["Detail Scale"].default_value = 1.4
        tree.links.new(coords, rings.inputs["Vector"])
        ramp = tree.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = [c * 0.55 for c in base[:3]] + [1]
        ramp.color_ramp.elements[1].color = [min(c * 1.15, 1) for c in base[:3]] + [1]
        tree.links.new(rings.outputs[1], ramp.inputs[0])
        tree.links.new(ramp.outputs[0], shader.inputs["Base Color"])
        _bump(tree, shader, rings.outputs[1], 0.12, 0.003 * size)


def build_material(name, preset, color=None, size=1.0, local_size=1.0, overrides=None):
    spec = PRESETS[preset]
    material = bpy.data.materials.new(name)
    util.enable_nodes(material)
    tree = material.node_tree
    shader = tree.nodes.get("Principled BSDF")
    base = util.rgba(color or spec["color"])
    shader.inputs["Base Color"].default_value = base
    skipped = _set_inputs(shader, spec["inputs"])
    if spec.get("emissive"):
        shader.inputs["Emission Color"].default_value = base
    if spec.get("glass"):
        util.set_if(material, "use_raytrace_refraction", True)
        util.set_if(material, "surface_render_method", "DITHERED")
        util.set_if(bpy.context.scene.eevee, "use_raytracing", True)
    if spec.get("detail"):
        _detail(spec["detail"], tree, shader, base, size, local_size)
    if overrides:
        skipped += _set_inputs(shader, overrides)
    material.diffuse_color = base
    return material, skipped


@command()
def apply_material(objects, preset, color=None, roughness=None, metallic=None, emission_strength=None):
    preset = preset.lower()
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset '{preset}'. Choose from: {', '.join(PRESETS)}")
    overrides = {k: v for k, v in (("Roughness", roughness), ("Metallic", metallic),
                                   ("Emission Strength", emission_strength)) if v is not None}
    applied, skipped = [], []
    for obj in util.subjects(objects):
        if not hasattr(obj.data, "materials"):
            continue
        local = max((max(c[i] for c in obj.bound_box) - min(c[i] for c in obj.bound_box)) for i in range(3))
        material, skip = build_material(f"{obj.name} {preset}", preset, color, max(obj.dimensions) or 1.0,
                                        local or 1.0, overrides)
        skipped += skip
        obj.data.materials.clear()
        obj.data.materials.append(material)
        applied.append(obj.name)
    if not applied:
        raise ValueError("None of those objects can take a material.")
    result = {"preset": preset, "applied_to": applied}
    if skipped:
        result["ignored_settings"] = sorted(set(skipped))
    return result


@command(mutates=False)
def list_presets():
    from .camera import SHOTS
    from .lighting import BACKDROPS, STYLES
    from .look import LOOKS
    return {
        "materials": list(PRESETS),
        "lighting_styles": STYLES,
        "backdrops": list(BACKDROPS),
        "camera_shots": {name: shot["about"] for name, shot in SHOTS.items()},
        "looks": {name: look["about"] for name, look in LOOKS.items()},
    }
