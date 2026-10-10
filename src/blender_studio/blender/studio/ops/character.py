"""Stylised people: a jointed figure built from simple parts, with pose presets and motion clips."""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .. import util
from ..commands import command
from .materials import build_material

# Proportions as fractions of total height. Feet stand on z = 0 and the figure faces the front (-Y).
STYLES = {
    "toy": dict(shape="capsule", hip=0.36, knee=0.19, ankle=0.045, chest=0.64, neck=0.69, head_r=0.15,
                shoulder_x=0.165, hip_x=0.065, elbow=0.50, wrist=0.38, limb_r=0.048, torso_r=0.12,
                material="plastic_matte", about="Rounded vinyl-toy figure with a big head. Friendly and cute."),
    "lowpoly": dict(shape="faceted", hip=0.50, knee=0.27, ankle=0.04, chest=0.79, neck=0.84, head_r=0.078,
                    shoulder_x=0.128, hip_x=0.058, elbow=0.61, wrist=0.45, limb_r=0.036, torso_r=0.095,
                    material="clay", about="Faceted figure with natural proportions. Matches low-poly scenes."),
    "blocky": dict(shape="box", hip=0.375, knee=0.19, ankle=0.0, chest=0.75, neck=0.75, head_r=0.125,
                   shoulder_x=0.1875, hip_x=0.0625, elbow=0.565, wrist=0.40, limb_r=0.0625, torso_r=0.125,
                   material="plastic_matte", about="Square voxel-game figure made of boxes."),
}

# Bone rotations in degrees as (bend forward, twist, raise sideways). A name without .L/.R applies to both
# sides, mirrored. '_root_thighs' and '_root_height' lower or lift the whole body.
POSES = {
    "stand": {"upper_arm": (0, 0, 7), "forearm": (8, 0, 0)},
    "t_pose": {"upper_arm": (0, 0, 90)},
    "wave": {"upper_arm.L": (0, 0, 7), "forearm.L": (8, 0, 0), "upper_arm.R": (0, 0, -148),
             "forearm.R": (0, 0, -32), "head": (0, 0, -6)},
    "cheer": {"upper_arm": (0, 0, 158), "forearm": (0, 0, 12), "head": (-10, 0, 0), "spine": (-4, 0, 0)},
    "walk": {"thigh.L": (28, 0, 0), "shin.L": (-12, 0, 0), "thigh.R": (-22, 0, 0), "shin.R": (-32, 0, 0),
             "upper_arm.L": (-26, 0, 6), "forearm.L": (14, 0, 0), "upper_arm.R": (26, 0, -6),
             "forearm.R": (30, 0, 0)},
    "run": {"thigh.L": (58, 0, 0), "shin.L": (-72, 0, 0), "thigh.R": (-30, 0, 0), "shin.R": (-58, 0, 0),
            "upper_arm.L": (-48, 0, 6), "forearm.L": (82, 0, 0), "upper_arm.R": (52, 0, -6),
            "forearm.R": (86, 0, 0), "spine": (12, 0, 0), "_root_height": 0.03},
    "sit": {"thigh": (88, 0, 0), "shin": (-88, 0, 0), "upper_arm": (22, 0, 5), "forearm": (58, 0, 0),
            "_root_thighs": -1.0},
    "point": {"upper_arm.R": (86, 0, -6), "upper_arm.L": (0, 0, 7), "forearm.L": (8, 0, 0)},
    "hands_on_hips": {"upper_arm": (0, 0, 42), "forearm": (0, 0, -98)},
    "think": {"upper_arm.R": (34, 0, -8), "forearm.R": (132, 0, 0), "upper_arm.L": (0, 0, 7),
              "forearm.L": (8, 0, 0), "head": (10, 0, -8)},
    "jump": {"thigh": (38, 0, 0), "shin": (-70, 0, 0), "upper_arm": (0, 0, 142), "forearm": (0, 0, 10),
             "head": (-8, 0, 0), "_root_height": 0.28},
}


def _swing(phase):
    return math.sin(phase), max(0.0, math.cos(phase))


def _clip_walk(t):
    phase = 2 * math.pi * t / 1.0
    pose = {"spine": (2, 4 * math.sin(phase), 0)}
    for side, shift, sign in ((".L", 0.0, 1), (".R", math.pi, -1)):
        swing, lift = _swing(phase + shift)
        pose["thigh" + side] = (28 * swing, 0, 0)
        pose["shin" + side] = (-(8 + 42 * lift), 0, 0)
        pose["upper_arm" + side] = (-24 * swing, 0, 7 * sign)
        pose["forearm" + side] = (16 + 10 * max(0.0, -swing), 0, 0)
    return pose, 0.012 * math.cos(2 * phase)


def _clip_run(t):
    phase = 2 * math.pi * t / 0.62
    pose = {"spine": (11, 6 * math.sin(phase), 0), "head": (-6, 0, 0)}
    for side, shift, sign in ((".L", 0.0, 1), (".R", math.pi, -1)):
        swing, lift = _swing(phase + shift)
        pose["thigh" + side] = (12 + 46 * swing, 0, 0)
        pose["shin" + side] = (-(18 + 78 * lift), 0, 0)
        pose["upper_arm" + side] = (-44 * swing, 0, 8 * sign)
        pose["forearm" + side] = (84, 0, 0)
    return pose, 0.03 * abs(math.sin(phase))


def _clip_wave(t):
    beat = math.sin(2 * math.pi * t * 2.2)
    return {"upper_arm.L": (0, 0, 7), "forearm.L": (8, 0, 0), "upper_arm.R": (0, 0, -146),
            "forearm.R": (0, 0, -30 + 24 * beat), "head": (0, 0, -6), "spine": (0, 0, -2)}, 0.0


def _clip_idle(t):
    breath = math.sin(2 * math.pi * t / 3.2)
    return {"spine": (1.5 * breath, 0, 0), "head": (0, 7 * math.sin(2 * math.pi * t / 5.0), 0),
            "upper_arm.L": (0, 0, 7 + breath), "upper_arm.R": (0, 0, -7 - breath),
            "forearm": (8, 0, 0)}, 0.002 * breath


def _clip_jump(t):
    u = (t % 1.3) / 1.3
    if u < 0.25:
        crouch, air = math.sin(math.pi * u / 0.25), 0.0
    elif u < 0.75:
        v = (u - 0.25) / 0.5
        crouch, air = 0.0, 4 * v * (1 - v)
    else:
        crouch, air = math.sin(math.pi * (u - 0.75) / 0.25) * 0.7, 0.0
    arms = 12 + 135 * air - 10 * crouch
    return {"thigh": (48 * crouch + 14 * air, 0, 0), "shin": (-92 * crouch - 30 * air, 0, 0),
            "spine": (14 * crouch - 5 * air, 0, 0), "upper_arm.L": (-20 * crouch, 0, arms),
            "upper_arm.R": (-20 * crouch, 0, -arms), "forearm": (10, 0, 0), "_crouch": crouch}, 0.32 * air


def _clip_dance(t):
    beat = 2 * math.pi * t / 1.0
    left, right = max(0.0, math.sin(beat)), max(0.0, -math.sin(beat))
    return {"spine": (0, 9 * math.sin(beat), 5 * math.sin(beat)), "head": (0, -8 * math.sin(beat), 0),
            "upper_arm.L": (10, 0, 95 + 50 * math.sin(beat)), "upper_arm.R": (10, 0, -95 + 50 * math.sin(beat)),
            "forearm.L": (0, 0, 40), "forearm.R": (0, 0, -40),
            "thigh.L": (22 * left, 0, 0), "shin.L": (-44 * left, 0, 0),
            "thigh.R": (22 * right, 0, 0), "shin.R": (-44 * right, 0, 0)}, 0.025 * abs(math.sin(beat))


CLIPS = {"walk": _clip_walk, "run": _clip_run, "wave": _clip_wave, "idle": _clip_idle, "jump": _clip_jump,
         "dance": _clip_dance}


def _segment(name, start, end, radius_start, radius_end, shape, flat=1.0):
    """One body part running from start to end, in world space."""
    start, end = Vector(start), Vector(end)
    length = max((end - start).length, 1e-5)
    bm = bmesh.new()
    if shape == "box":
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(2 * radius_start, 2 * radius_start * flat, length), verts=bm.verts)
    else:
        faceted = shape == "faceted"
        bmesh.ops.create_cone(bm, cap_ends=faceted, segments=7 if faceted else 20,
                              radius1=radius_start, radius2=radius_end, depth=length)
        if not faceted:
            for radius, z in ((radius_start, -length / 2), (radius_end, length / 2)):
                bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=radius,
                                          matrix=Matrix.Translation((0, 0, z)))
        bmesh.ops.scale(bm, vec=(1, flat, 1), verts=bm.verts)
    return _part(name, bm, shape == "capsule",
                 Matrix.Translation((start + end) / 2)
                 @ Vector((0, 0, 1)).rotation_difference((end - start).normalized()).to_matrix().to_4x4())


def _ball(name, center, radius, shape, stretch=(1, 1, 1), keep=None):
    bm = bmesh.new()
    if shape == "box":
        bmesh.ops.create_cube(bm, size=2 * radius)
    elif shape == "faceted":
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius)
    else:
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=radius)
    if keep:
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep(v.co)], context="VERTS")
    bmesh.ops.scale(bm, vec=stretch, verts=bm.verts)
    return _part(name, bm, shape == "capsule", Matrix.Translation(center))


def _part(name, bm, smooth, matrix):
    for face in bm.faces:
        face.smooth = smooth
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.matrix_world = matrix
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _build_armature(name, spec, h):
    data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    front = Vector((0, -1, 0))

    def bone(bone_name, head, tail, parent=None):
        edit = data.edit_bones.new(bone_name)
        edit.head, edit.tail = Vector(head) * h, Vector(tail) * h
        # Roll every bone the same way so that a positive first angle always bends forward.
        edit.align_roll(front)
        if parent:
            edit.parent = data.edit_bones[parent]
        return edit

    waist = spec["hip"] + 0.4 * (spec["chest"] - spec["hip"])
    bone("hips", (0, 0, spec["hip"]), (0, 0, waist))
    bone("spine", (0, 0, waist), (0, 0, spec["chest"]), "hips")
    bone("head", (0, 0, spec["neck"]), (0, 0, spec["neck"] + 2 * spec["head_r"]), "spine")
    for side, sign in ((".L", 1), (".R", -1)):
        sx, hx = sign * spec["shoulder_x"], sign * spec["hip_x"]
        bone("upper_arm" + side, (sx, 0, spec["chest"] - spec["limb_r"] * 0.4), (sx, 0, spec["elbow"]), "spine")
        bone("forearm" + side, (sx, 0, spec["elbow"]), (sx, 0, spec["wrist"]), "upper_arm" + side)
        bone("thigh" + side, (hx, 0, spec["hip"]), (hx, 0, spec["knee"]), "hips")
        bone("shin" + side, (hx, 0, spec["knee"]), (hx, 0, max(spec["ankle"], 0.005)), "thigh" + side)
    bpy.ops.object.mode_set(mode="OBJECT")
    for pbone in arm.pose.bones:
        pbone.rotation_mode = "XYZ"
    data.display_type = "STICK"
    return arm


@command()
def create_character(name="Character", style="toy", height=1.7, skin="#e2b091", top="#3f7fd0", bottom="#2c3550",
                     shoes="#f1eee8", hair="#3a2a20", location=None, facing_deg=0.0, pose="stand"):
    style = style.lower()
    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'. Choose from: {', '.join(STYLES)}")
    if bpy.data.objects.get(name):
        raise ValueError(f"An object named '{name}' already exists. Pick another name or delete it first.")
    spec, h = STYLES[style], float(height)
    shape, r, tr = spec["shape"], spec["limb_r"] * h, spec["torso_r"] * h
    arm = _build_armature(name, spec, h)
    arm["studio_character"] = style
    arm["studio_height"] = h
    arm["studio_thigh"] = (spec["hip"] - spec["knee"]) * h

    colours = {"skin": skin, "top": top, "bottom": bottom, "shoes": shoes, "hair": hair, "eyes": "#17171c"}
    materials = {}

    def material(role):
        if role not in materials:
            preset = "plastic_glossy" if role == "eyes" else spec["material"]
            materials[role], _ = build_material(f"{name} {role}", preset, colours[role], h, h)
        return materials[role]

    parts = []

    def attach(obj, bone_name, role):
        obj.data.materials.append(material(role))
        obj["studio_character"] = name
        parts.append((obj, bone_name, obj.matrix_world.copy()))

    def z(key, extra=0.0):
        return spec[key] * h + extra

    waist = z("hip") + 0.4 * (z("chest") - z("hip"))
    flat = 0.5 if shape == "box" else 0.66
    attach(_segment(f"{name} Pelvis", (0, 0, z("hip", -r * 0.4)), (0, 0, waist), tr * 0.94, tr * 0.94, shape, flat),
           "hips", "bottom")
    attach(_segment(f"{name} Torso", (0, 0, waist), (0, 0, z("chest")), tr * 0.94, tr, shape, flat), "spine", "top")
    if shape != "box":
        attach(_segment(f"{name} Neck", (0, 0, z("chest")), (0, 0, z("neck", r * 0.5)), r * 0.8, r * 0.8, shape),
               "spine", "skin")

    head_r = spec["head_r"] * h
    head_c = Vector((0, 0, z("neck") + head_r))
    attach(_ball(f"{name} Head", head_c, head_r, shape), "head", "skin")
    if hair and str(hair).lower() != "none":
        if shape == "box":
            attach(_ball(f"{name} Hair", head_c + Vector((0, 0, head_r * 0.82)), head_r * 1.04, shape,
                         stretch=(1, 1, 0.24)), "head", "hair")
            attach(_ball(f"{name} Hair Back", head_c + Vector((0, head_r * 0.92, 0.1 * head_r)), head_r * 1.04,
                         shape, stretch=(1, 0.14, 0.9)), "head", "hair")
        else:
            attach(_ball(f"{name} Hair", head_c, head_r * 1.07, shape,
                         keep=lambda co: co.z > 0.18 * head_r or co.y > 0.3 * head_r), "head", "hair")
    for side, sign in ((".L", 1), (".R", -1)):
        eye = head_c + Vector((sign * 0.36 * head_r, -0.92 * head_r, 0.06 * head_r))
        attach(_ball(f"{name} Eye{side}", eye, head_r * (0.1 if shape == "box" else 0.13), shape), "head", "eyes")

        sx, hx = sign * spec["shoulder_x"] * h, sign * spec["hip_x"] * h
        attach(_segment(f"{name} UpperArm{side}", (sx, 0, z("chest", -r * 0.4)), (sx, 0, z("elbow")), r, r * 0.95,
                        shape), "upper_arm" + side, "top")
        attach(_segment(f"{name} Forearm{side}", (sx, 0, z("elbow")), (sx, 0, z("wrist")), r * 0.92, r * 0.85,
                        shape), "forearm" + side, "skin")
        attach(_ball(f"{name} Hand{side}", (sx, 0, z("wrist", -r * 0.6)), r * (1.0 if shape == "box" else 1.15),
                     shape), "forearm" + side, "skin")
        attach(_segment(f"{name} Thigh{side}", (hx, 0, z("hip")), (hx, 0, z("knee")), r * 1.2, r * 1.1, shape),
               "thigh" + side, "bottom")
        ankle = max(z("ankle"), r * 0.9 if shape == "box" else z("ankle"))
        attach(_segment(f"{name} Shin{side}", (hx, 0, z("knee")), (hx, 0, ankle), r * 1.1, r * 0.95, shape),
               "shin" + side, "bottom")
        sole = max(z("ankle") * 1.5, r * 0.9)
        if shape == "box":
            attach(_ball(f"{name} Foot{side}", (hx, 0, sole / 2), r * 1.04, shape,
                         stretch=(1, 1, sole / (2 * r * 1.04))), "shin" + side, "shoes")
        else:
            attach(_ball(f"{name} Foot{side}", (hx, -r * 0.9, sole / 2), r * 1.25, shape,
                         stretch=(1, 1.75, sole / (2 * r * 1.25))), "shin" + side, "shoes")

    bpy.context.view_layer.update()
    for obj, bone_name, world in parts:
        obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", bone_name
    bpy.context.view_layer.update()
    for obj, _, world in parts:
        obj.matrix_world = world
    arm.location = location or (0, 0, 0)
    arm.rotation_euler.z = math.radians(facing_deg)
    _set_pose(arm, POSES.get(pose) or POSES["stand"])
    bpy.context.view_layer.update()
    return {"name": name, "style": style, "height": h, "parts": [obj.name for obj, _, _ in parts],
            "poses": list(POSES), "clips": list(CLIPS),
            "tip": f"Use '{name}' as the object name to move, frame or recolour the whole figure."}


def _rotation(pose, bone_name):
    if bone_name in pose:
        return pose[bone_name]
    base, _, side = bone_name.partition(".")
    if base in pose:
        x, y, zr = pose[base]
        return (x, y, zr) if side != "R" else (x, -y, -zr)
    return (0, 0, 0)


def _set_pose(arm, pose, lift=0.0, frame=None):
    if arm.get("studio_character") == "human":
        from .human import set_pose
        return set_pose(arm, pose, lift, frame)
    for pbone in arm.pose.bones:
        pbone.rotation_mode = "XYZ"
        pbone.rotation_euler = [math.radians(a) for a in _rotation(pose, pbone.name)]
        if frame is not None:
            pbone.keyframe_insert("rotation_euler", frame=frame)
    hips = arm.pose.bones.get("hips")
    if hips:
        height, thigh = arm.get("studio_height", 1.7), arm.get("studio_thigh", 0.4)
        drop = pose.get("_root_height", 0.0) * height + pose.get("_root_thighs", 0.0) * thigh + lift * height
        # Crouching bends the knees, so sink the body by the height the legs lose.
        crouch = pose.get("_crouch", 0.0)
        drop -= crouch * thigh * 0.55
        hips.location = (0, drop, 0)
        if frame is not None:
            hips.keyframe_insert("location", frame=frame)


def _rig(name):
    obj = util.get_object(name)
    if obj.type != "ARMATURE":
        rigs = [o.name for o in bpy.data.objects if o.type == "ARMATURE"]
        raise ValueError(f"'{name}' is not a character or rig. Rigs in the scene: {', '.join(rigs) or 'none'}")
    return obj


@command()
def pose_character(character, pose=None, bones=None):
    """Put a figure in a preset pose, and/or set individual bones as {bone: [x, y, z] degrees}."""
    arm = _rig(character)
    arm.animation_data_clear()
    if pose:
        if "studio_character" not in arm:
            raise ValueError("Pose presets only fit figures made with create_character or create_human. "
                             "For an imported rig, pass `bones` with rotations for its own bone names.")
        if pose not in POSES:
            raise ValueError(f"Unknown pose '{pose}'. Choose from: {', '.join(POSES)}")
        _set_pose(arm, POSES[pose])
    unknown = [b for b in (bones or {}) if b not in arm.pose.bones]
    if unknown:
        raise ValueError(f"No such bones: {', '.join(unknown)}. Available: "
                         f"{', '.join(b.name for b in arm.pose.bones[:60])}")
    for bone_name, rotation in (bones or {}).items():
        pbone = arm.pose.bones[bone_name]
        pbone.rotation_mode = "XYZ"
        pbone.rotation_euler = [math.radians(a) for a in rotation]
    bpy.context.view_layer.update()
    return {"character": arm.name, "pose": pose, "bones_set": list(bones or {})}


@command()
def animate_character(character, clip, seconds=4.0, start_seconds=0.0, distance=0.0):
    """Play a motion clip on a create_character figure. distance moves it forward that many metres meanwhile."""
    arm = _rig(character)
    if "studio_character" not in arm:
        raise ValueError("Motion clips only fit figures made with create_character or create_human. For an imported "
                         "character use list_animations and play_animation.")
    if clip not in CLIPS:
        raise ValueError(f"Unknown clip '{clip}'. Choose from: {', '.join(CLIPS)}")
    first, last = util.to_frame(start_seconds), util.to_frame(start_seconds + seconds)
    fps = util.fps()
    for frame in range(first, last + 1, 2):
        pose, lift = CLIPS[clip]((frame - first) / fps)
        _set_pose(arm, pose, lift, frame)
    if distance:
        forward = Vector((math.sin(arm.rotation_euler.z), -math.cos(arm.rotation_euler.z), 0))
        with util.linear_keys():
            arm.keyframe_insert("location", frame=first)
            arm.location = arm.location + forward * distance
            arm.keyframe_insert("location", frame=last)
    util.extend_timeline(last)
    bpy.context.scene.frame_set(first)
    return {"character": arm.name, "clip": clip, "frames": [first, last], "seconds": seconds,
            "tip": "render_animation makes the video; render_preview(at_seconds=...) shows one moment."}


@command(mutates=False)
def list_animations():
    """Rigs in the scene, their bones, and the motion clips that came with imported files."""
    actions = [{"name": a.name, "seconds": round((a.frame_range[1] - a.frame_range[0]) / util.fps(), 2)}
               for a in bpy.data.actions]
    rigs = []
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            current = obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None
            rigs.append({"name": obj.name, "made_by_create_character": "studio_character" in obj,
                         "playing": current, "bones": [b.name for b in obj.pose.bones][:70]})
    return {"rigs": rigs, "clips_in_file": actions, "preset_poses": list(POSES), "preset_clips": list(CLIPS)}


@command()
def play_animation(target, clip):
    """Play a motion clip that came with an imported file on a rig or object."""
    obj = util.get_object(target)
    action = bpy.data.actions.get(clip)
    if action is None:
        raise ValueError(f"No clip named '{clip}'. Available: {', '.join(a.name for a in bpy.data.actions) or 'none'}")
    if obj.animation_data is None:
        obj.animation_data_create()
    for track in list(obj.animation_data.nla_tracks):
        track.mute = True
    obj.animation_data.action = action
    if hasattr(obj.animation_data, "action_slot") and getattr(action, "slots", None):
        try:
            obj.animation_data.action_slot = action.slots[0]
        except (TypeError, ValueError):
            pass
    start, end = (int(round(v)) for v in action.frame_range)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = start, max(end, start + 1)
    scene["studio_animated"] = True
    scene.frame_set(start)
    return {"target": obj.name, "clip": action.name, "seconds": round((end - start) / util.fps(), 2)}
