"""Scene lint: catches the mistakes that are obvious to a person looking at the screen."""
import bpy
from bpy_extras.object_utils import world_to_camera_view

from .. import util
from ..commands import command


def _box(obj):
    lo, hi, _, _ = util.bounds([obj])
    return lo, hi


def _touching(a, b, slack):
    return all(a[0][i] - slack <= b[1][i] and b[0][i] - slack <= a[1][i] for i in range(3))


@command(mutates=False)
def scene_check():
    scene = bpy.context.scene
    problems, suggestions = [], []
    subjects = util.subjects()
    if not subjects:
        return {"problems": ["The scene is empty."], "suggestions": []}
    lo, hi, _, radius = util.bounds(subjects)

    lights = [o for o in scene.objects if o.type == "LIGHT" and not o.hide_render]
    emissive = any(
        slot.material and slot.material.node_tree and any(
            n.type == "BSDF_PRINCIPLED" and n.inputs["Emission Strength"].default_value > 0
            for n in slot.material.node_tree.nodes)
        for o in subjects for slot in o.material_slots)
    if not lights and not emissive:
        world_lit = scene.world is not None and scene.world.node_tree is not None and any(
            n.type in ("TEX_ENVIRONMENT", "TEX_SKY") for n in scene.world.node_tree.nodes)
        if not world_lit:
            problems.append("No lights. The render will be flat or black. Call studio_lighting.")

    cam = scene.camera
    if cam is None:
        problems.append("No camera. Call frame_camera.")
    else:
        points = [world_to_camera_view(scene, cam, c) for c in util.bbox_corners(subjects)]
        visible = [p for p in points if p.z > 0 and 0 <= p.x <= 1 and 0 <= p.y <= 1]
        if not visible:
            problems.append("The camera cannot see the subject at all. Call frame_camera.")
        else:
            cut = 1 - len(visible) / len(points)
            xs, ys = [p.x for p in points], [p.y for p in points]
            extent = max(max(xs) - min(xs), max(ys) - min(ys))
            if cut > 0.35:
                problems.append(f"About {cut:.0%} of the subject is outside the frame.")
            elif extent < 0.3:
                suggestions.append("The subject fills under a third of the frame; move in or use 'closeup'.")

    backdrop = bpy.data.collections.get(util.BACKDROP)
    floor = backdrop.objects[0].location.z if backdrop and backdrop.objects else None
    if floor is None:
        suggestions.append("Nothing to stand on or catch shadows. Call add_backdrop.")
    ground = lo.z if floor is None else floor
    slack = radius * 0.02
    boxes = {o.name: _box(o) for o in subjects}
    for obj in subjects:
        box = boxes[obj.name]
        if floor is not None and box[1].z < floor - slack:
            problems.append(f"'{obj.name}' is entirely below the floor.")
        elif floor is not None and box[0].z < floor - slack * 2:
            problems.append(f"'{obj.name}' sinks {floor - box[0].z:.3f} m into the floor.")
        elif box[0].z > ground + slack and not any(
                _touching(box, other, slack) for name, other in boxes.items() if name != obj.name):
            problems.append(f"'{obj.name}' is floating {box[0].z - ground:.3f} m above the ground, touching nothing.")

    seen = {}
    for obj in subjects:
        key = (tuple(round(v, 3) for v in obj.matrix_world.translation), tuple(round(v, 3) for v in obj.dimensions))
        if key in seen:
            problems.append(f"'{obj.name}' sits exactly on top of '{seen[key]}' (duplicate?).")
        seen[key] = obj.name

    bare = [o.name for o in subjects if hasattr(o.data, "materials") and not any(m for m in o.data.materials)]
    if bare:
        problems.append(f"No material on: {', '.join(bare[:8])}. They will render plain grey.")

    hard = [o.name for o in subjects if o.type == "MESH" and len(o.data.polygons) < 2000
            and "studio_character" not in o
            and not any(m.type == "BEVEL" for m in o.modifiers)
            and any(not p.use_smooth for p in o.data.polygons)]
    if hard:
        suggestions.append(f"Razor-sharp edges on: {', '.join(hard[:8])}. add_polish gives them soft highlights.")

    tiny = [o.name for o in subjects if max(o.dimensions) < radius * 0.01 and "studio_character" not in o]
    if tiny:
        suggestions.append(f"Very small compared to the scene, may be invisible: {', '.join(tiny[:8])}.")

    if scene.view_settings.look in ("None", "") and scene.view_settings.view_transform != "Standard":
        suggestions.append("No look chosen yet. Call set_look for better contrast.")

    return {"problems": problems, "suggestions": suggestions,
            "verdict": "Looks sound. Render and judge by eye." if not problems else "Fix the problems, then render."}
