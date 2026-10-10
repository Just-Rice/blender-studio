"""Realistic human bodies through the free MPFB (MakeHuman) add-on, dressed in a painted-on outfit."""
import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from .. import util
from ..commands import command
from .materials import build_material

MODULE = "bl_ext.blender_org.mpfb"
AGES = {"young": 0.5, "adult": 0.62, "elder": 0.9}
GENDERS = {"female": 0.0, "neutral": 0.5, "male": 1.0}

# Which MPFB bone carries each of the simple figure's joints.
BONES = {"spine": "spine04", "head": "head", "upper_arm.L": "upperarm01.L", "upper_arm.R": "upperarm01.R",
         "forearm.L": "lowerarm01.L", "forearm.R": "lowerarm01.R", "thigh.L": "upperleg01.L",
         "thigh.R": "upperleg01.R", "shin.L": "lowerleg01.L", "shin.R": "lowerleg01.R"}
PARENTS = {"spine": None, "head": "spine", "upper_arm.L": "spine", "upper_arm.R": "spine",
           "forearm.L": "upper_arm.L", "forearm.R": "upper_arm.R", "thigh.L": None, "thigh.R": None,
           "shin.L": "thigh.L", "shin.R": "thigh.R"}
# Body regions, by the bone that moves them, and the part of the outfit that covers each.
OUTFIT = (("shoes", ("foot", "toe")), ("bottom", ("pelvis", "upperleg", "lowerleg", "spine05")),
          ("top", ("spine", "breast", "clavicle", "shoulder", "upperarm")))


def _ensure_mpfb():
    def enable():
        import addon_utils
        addon_utils.enable(MODULE, default_set=False)
        from bl_ext.blender_org.mpfb.services.humanservice import HumanService  # noqa: F401
    try:
        enable()
        return
    except Exception:
        pass
    try:
        bpy.context.preferences.system.use_online_access = True
        bpy.ops.extensions.repo_sync_all()
        bpy.ops.extensions.package_install(repo_index=0, pkg_id="mpfb", enable_on_install=True)
        enable()
    except Exception as exc:
        raise ValueError("create_human needs the free MPFB add-on, and installing it automatically failed "
                         f"({exc}). In Blender open Edit > Preferences > Get Extensions, install 'MPFB', "
                         "then try again. create_character works without it.") from None


def _toy_rotations(pose):
    """World-space turn of each joint for a pose written for the simple figure (limbs hanging straight down)."""
    from .character import _rotation
    front = Vector((0, -1, 0))
    done = {}

    def solve(joint):
        if joint in done:
            return done[joint]
        direction = Vector((0, 0, 1)) if joint in ("spine", "head") else Vector((0, 0, -1))
        basis = Matrix((direction.cross(front), direction, front)).transposed()
        local = Euler([math.radians(a) for a in _rotation(pose, joint)], "XYZ").to_matrix()
        parent = solve(PARENTS[joint]) if PARENTS[joint] else Matrix.Identity(3)
        done[joint] = parent @ basis @ local @ basis.transposed()
        return done[joint]

    for joint in BONES:
        solve(joint)
    return done


def set_pose(arm, pose, lift=0.0, frame=None):
    """Retarget a simple-figure pose onto the MPFB skeleton, working out every bone by hand so no
    scene refresh is needed per bone."""
    turns = _toy_rotations(pose)
    targets = {bone: joint for joint, bone in BONES.items() if bone in arm.pose.bones}
    height, thigh = arm["studio_height"], arm["studio_thigh"]
    rise = (pose.get("_root_height", 0.0) * height + pose.get("_root_thighs", 0.0) * thigh + lift * height
            - pose.get("_crouch", 0.0) * thigh * 0.55) / max(arm.scale.z, 1e-6)
    posed = {}
    for bone in arm.data.bones:  # parents always come before their children
        pbone = arm.pose.bones[bone.name]
        rest = bone.matrix_local
        base = posed[bone.parent.name] @ bone.parent.matrix_local.inverted() @ rest if bone.parent else rest
        if bone.parent is None:
            pbone.location = rest.to_3x3().inverted() @ Vector((0, 0, rise))
            base = Matrix.Translation((0, 0, rise)) @ rest
            if frame is not None:
                pbone.keyframe_insert("location", frame=frame)
        if bone.name in targets:
            joint = targets[bone.name]
            turn = turns[joint]
            if "arm" in joint:
                # MPFB rests with the arms held out; bring them to the simple figure's arms-down rest first.
                along = (rest.to_3x3() @ Vector((0, 1, 0))).normalized()
                turn = turn @ along.rotation_difference(Vector((0, 0, -1))).to_matrix()
            wanted = (turn @ rest.to_3x3()).to_4x4()
            wanted.translation = base.translation
            pbone.rotation_mode = "QUATERNION"
            pbone.rotation_quaternion = (base.inverted() @ wanted).to_quaternion()
            if frame is not None:
                pbone.keyframe_insert("rotation_quaternion", frame=frame)
            base = wanted
        posed[bone.name] = base


def _dress(body, colours, name, height):
    """Paint an outfit straight onto the body: each face takes the material of the bone that moves it most."""
    roles = ["skin", "top", "bottom", "shoes", "hair"]
    presets = {"skin": "skin", "top": "plastic_matte", "bottom": "plastic_matte", "shoes": "plastic_matte",
               "hair": "plastic_matte"}
    for role in roles:
        cloth = {"Roughness": 0.9, "Sheen Weight": 0.4} if role in ("top", "bottom") else None
        material, _ = build_material(f"{name} {role}", presets[role], colours[role], height, height, cloth)
        body.data.materials.append(material)
    region = {}
    for group in body.vertex_groups:
        for role, prefixes in OUTFIT:
            if group.name.startswith(prefixes):
                region[group.index] = roles.index(role)
                break
    scalp = body.vertex_groups.get("scalp")
    scalp_index = scalp.index if scalp and colours["hair"] else -1
    vertex_role = []
    for vert in body.data.vertices:
        best, weight, hairy = 0, 0.0, False
        totals = {}
        for membership in vert.groups:
            if membership.group == scalp_index and membership.weight > 0.5:
                hairy = True
            role = region.get(membership.group)
            if role is not None:
                totals[role] = totals.get(role, 0.0) + membership.weight
        for role, total in totals.items():
            if total > weight:
                best, weight = role, total
        vertex_role.append(roles.index("hair") if hairy else (best if weight > 0.5 else 0))
    for poly in body.data.polygons:
        votes = [vertex_role[v] for v in poly.vertices]
        poly.material_index = max(set(votes), key=votes.count)
        poly.use_smooth = True


def _eyes(arm, body, name, height):
    for side in (".L", ".R"):
        bone = arm.data.bones.get("eye" + side)
        if bone is None:
            continue
        radius = height * 0.0072
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius)
        mesh = bpy.data.meshes.new(f"{name} Eye{side}")
        for face in bm.faces:
            face.smooth = True
        bm.to_mesh(mesh)
        bm.free()
        eye = bpy.data.objects.new(f"{name} Eye{side}", mesh)
        material, _ = build_material(f"{name} eyes", "plastic_glossy", "#2a2320", height, height)
        mesh.materials.append(material)
        eye["studio_character"] = name
        bpy.context.scene.collection.objects.link(eye)
        world = arm.matrix_world @ Matrix.Translation(bone.tail_local)
        eye.parent, eye.parent_type, eye.parent_bone = arm, "BONE", "head"
        bpy.context.view_layer.update()
        eye.matrix_world = world


@command()
def create_human(name="Human", gender="neutral", age="adult", muscle=0.5, weight=0.5, height=1.7,
                 skin="#c98f6b", top="#3f6fa8", bottom="#2b3040", shoes="#1d1d21", hair="#2a1d16",
                 location=None, facing_deg=0.0, pose="stand"):
    from .character import POSES, _set_pose
    if bpy.data.objects.get(name):
        raise ValueError(f"An object named '{name}' already exists. Pick another name or delete it first.")
    if age not in AGES:
        raise ValueError(f"Unknown age '{age}'. Choose from: {', '.join(AGES)}")
    amount = GENDERS.get(gender) if isinstance(gender, str) else float(gender)
    if amount is None:
        raise ValueError(f"Unknown gender '{gender}'. Choose from: {', '.join(GENDERS)}, or a number 0-1.")
    _ensure_mpfb()
    from bl_ext.blender_org.mpfb.services.humanservice import HumanService
    from bl_ext.blender_org.mpfb.services.targetservice import TargetService

    macro = TargetService.get_default_macro_info_dict()
    macro.update(gender=amount, age=AGES[age], muscle=min(max(muscle, 0.0), 1.0),
                 weight=min(max(weight, 0.0), 1.0))
    before = set(bpy.data.objects)
    body = HumanService.create_human(mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True,
                                     feet_on_ground=True, scale=0.1, macro_detail_dict=macro)
    HumanService.add_builtin_rig(body, "default", import_weights=True)
    arm = body.parent
    if arm is None or arm.type != "ARMATURE":
        raise ValueError("MPFB made the body but not its skeleton; this MPFB version is not supported.")
    bpy.context.view_layer.update()
    natural = max(body.dimensions.z, 1e-6)
    hair_colour = None if str(hair).lower() == "none" else hair
    _dress(body, {"skin": skin, "top": top, "bottom": bottom, "shoes": shoes, "hair": hair_colour or skin},
           name, height)
    arm.name = name
    body.name = f"{name} Body"
    body["studio_character"] = name
    arm.data.display_type = "STICK"
    arm["studio_character"] = "human"
    arm["studio_height"] = float(height)
    hip, knee = arm.data.bones.get("upperleg01.L"), arm.data.bones.get("lowerleg01.L")
    arm["studio_thigh"] = ((hip.head_local - knee.head_local).length if hip and knee else natural * 0.25) \
        * height / natural
    _eyes(arm, body, name, natural)
    smooth = body.modifiers.new("Studio Smooth", "SUBSURF")
    smooth.levels = smooth.render_levels = 1
    arm.scale = [height / natural] * 3
    arm.location = location or (0, 0, 0)
    arm.rotation_euler.z = math.radians(facing_deg)
    for extra in set(bpy.data.objects) - before:
        if extra not in (arm, body) and "studio_character" not in extra and extra.parent is None:
            bpy.data.objects.remove(extra, do_unlink=True)
    _set_pose(arm, POSES.get(pose) or POSES["stand"])
    bpy.context.view_layer.update()
    return {"name": name, "height": height, "gender": gender, "age": age, "poses": list(POSES),
            "outfit": "painted on: short-sleeved top, long trousers, shoes",
            "tip": "Best at medium distance. Works with pose_character presets and animate_character clips."}
