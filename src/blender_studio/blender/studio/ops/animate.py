"""Motion: turntables, camera moves, simple object animation, and physics that Blender works out itself."""
import math

import bmesh
import bpy
from mathutils import Vector

from .. import util
from ..commands import command
from .sculpt import freeze

KINDS = {
    "turntable": "The subject spins once on the spot while the camera and lights stay put. Loops seamlessly.",
    "camera_orbit": "The camera circles the subject. amount is degrees (default 360).",
    "dolly": "The camera glides toward the subject. amount is the fraction of the distance covered (default 0.35).",
    "bounce": "The target hops up and down. amount is the hop height in metres.",
    "spin": "The target turns on its own axis. amount is the number of full turns (default 1).",
    "float": "The target bobs and sways gently, as if hovering. amount is the bob height in metres.",
    "grow": "The target pops in from nothing with a little overshoot.",
    "light_fade": "The lights come up from darkness.",
}


def _pivot(name, location):
    old = bpy.data.objects.get(name)
    if old is not None:
        for child in list(old.children):
            world = child.matrix_world.copy()
            child.parent = None
            child.matrix_world = world
        bpy.data.objects.remove(old, do_unlink=True)
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_size = 0.1
    empty.location = location
    util.link_only(empty, util.CAMERAS)
    bpy.context.view_layer.update()
    return empty


def _adopt(pivot, obj):
    obj.parent = pivot
    obj.matrix_parent_inverse = pivot.matrix_world.inverted()


def _targets(target):
    if not target:
        raise ValueError("This kind of animation needs `target`: the name of the object to move.")
    return util.roots(util.subjects(target))


@command()
def animate(kind, target=None, seconds=4.0, amount=None, start_seconds=0.0):
    kind = kind.lower()
    if kind not in KINDS:
        raise ValueError(f"Unknown kind '{kind}'. Choose from: {', '.join(KINDS)}")
    scene = bpy.context.scene
    first, last = util.to_frame(start_seconds), util.to_frame(start_seconds + seconds)
    fps = util.fps()
    moved = []

    if kind == "turntable":
        targets = util.require_subjects(target)
        lo, _, center, _ = util.bounds(targets)
        pivot = _pivot("Turntable", (center.x, center.y, lo.z))
        for obj in util.roots(targets):
            _adopt(pivot, obj)
            moved.append(obj.name)
        with util.linear_keys():
            pivot.keyframe_insert("rotation_euler", frame=first)
            pivot.rotation_euler.z = 2 * math.pi
            # One frame past the end, so the last frame is not a repeat of the first when looped.
            pivot.keyframe_insert("rotation_euler", frame=last + 1)
    elif kind in ("camera_orbit", "dolly"):
        cam = scene.camera
        if cam is None:
            raise ValueError("There is no camera yet. Call frame_camera first.")
        _, _, center, _ = util.bounds(util.require_subjects(target))
        moved.append(cam.name)
        if kind == "camera_orbit":
            pivot = _pivot("Camera Orbit", center)
            _adopt(pivot, cam)
            turn = math.radians(360.0 if amount is None else amount)
            full = abs(abs(turn) - 2 * math.pi) < 1e-3
            if full:
                with util.linear_keys():
                    pivot.keyframe_insert("rotation_euler", frame=first)
                    pivot.rotation_euler.z = turn
                    pivot.keyframe_insert("rotation_euler", frame=last + 1)
            else:
                pivot.keyframe_insert("rotation_euler", frame=first)
                pivot.rotation_euler.z = turn
                pivot.keyframe_insert("rotation_euler", frame=last)
        else:
            cam.keyframe_insert("location", frame=first)
            moved_to = cam.matrix_world.copy()
            moved_to.translation += (center - moved_to.translation) * (0.35 if amount is None else amount)
            cam.matrix_world = moved_to
            cam.keyframe_insert("location", frame=last)
    elif kind == "light_fade":
        lights = [o for o in util.ensure_collection(util.LIGHTS).objects if o.type == "LIGHT"]
        if not lights:
            raise ValueError("There are no studio lights to fade. Call studio_lighting first.")
        for light in lights:
            full = light.data.energy
            light.data.energy = 0.0
            light.data.keyframe_insert("energy", frame=first)
            light.data.energy = full
            light.data.keyframe_insert("energy", frame=last)
            moved.append(light.name)
    else:
        for obj in _targets(target):
            moved.append(obj.name)
            base, size = obj.location.copy(), max(obj.dimensions) or 1.0
            if kind == "spin":
                with util.linear_keys():
                    obj.keyframe_insert("rotation_euler", frame=first)
                    obj.rotation_euler.z += 2 * math.pi * (1.0 if amount is None else amount)
                    obj.keyframe_insert("rotation_euler", frame=last + 1)
            elif kind == "grow":
                full = obj.scale.copy()
                for at, factor in ((0.0, 0.001), (0.6, 1.12), (0.8, 0.96), (1.0, 1.0)):
                    obj.scale = full * factor
                    obj.keyframe_insert("scale", frame=first + round((last - first) * at))
            else:
                height = amount if amount is not None else size * (0.6 if kind == "bounce" else 0.12)
                for frame in range(first, last + 1, 2):
                    t = (frame - first) / fps
                    if kind == "bounce":
                        obj.location.z = base.z + height * abs(math.sin(math.pi * t / 0.7))
                    else:
                        obj.location.z = base.z + height * (0.5 + 0.5 * math.sin(2 * math.pi * t / 3.0))
                        obj.rotation_euler.z += math.radians(0.6) * math.cos(2 * math.pi * t / 4.0)
                        obj.keyframe_insert("rotation_euler", frame=frame)
                    obj.keyframe_insert("location", frame=frame)
    util.extend_timeline(last)
    scene.frame_set(first)
    return {"kind": kind, "moved": moved, "frames": [first, last], "seconds": seconds,
            "tip": "render_animation makes the video; render_preview(at_seconds=...) shows one moment."}


@command()
def clear_animation(objects=None):
    """Remove motion from the named objects, or from everything."""
    scene = bpy.context.scene
    targets = [util.get_object(n) for n in util.as_list(objects)] if objects else list(bpy.data.objects)
    for obj in targets:
        obj.animation_data_clear()
        if obj.data is not None and hasattr(obj.data, "animation_data_clear"):
            obj.data.animation_data_clear()
    if not objects:
        for name in ("Turntable", "Camera Orbit"):
            if bpy.data.objects.get(name):
                _pivot(name, (0, 0, 0))
                bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
        scene.frame_end = 1
        scene["studio_animated"] = False
    scene.frame_set(1)
    return {"cleared": [o.name for o in targets][:40] if objects else "everything"}


@command()
def set_time(seconds):
    """Move to a moment in the animation, so the scene can be inspected or rendered there."""
    frame = util.to_frame(seconds)
    bpy.context.scene.frame_set(frame)
    return {"seconds": seconds, "frame": frame, "timeline_seconds": round((bpy.context.scene.frame_end - 1) / util.fps(), 2)}


def _colliders(active):
    """Everything the moving things can land on: other subjects and the backdrop."""
    backdrop = bpy.data.collections.get(util.BACKDROP)
    others = [o for o in util.subjects() if o not in active and o.type == "MESH"]
    return others + [o for o in (backdrop.objects if backdrop else []) if o.type == "MESH"]


def _temporary_ground(active):
    lo, _, center, radius = util.bounds(util.subjects() or active)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=radius * 60)
    mesh = bpy.data.meshes.new("Studio Physics Ground")
    bm.to_mesh(mesh)
    bm.free()
    ground = bpy.data.objects.new("Studio Physics Ground", mesh)
    ground.location = (center.x, center.y, lo.z)
    ground.hide_render = True
    bpy.context.scene.collection.objects.link(ground)
    return ground


@command()
def drop_objects(objects, seconds=3.0, bounciness=0.25, friction=0.6, keep_animation=True, start_seconds=0.0):
    """Let objects fall and tumble under gravity until they settle, landing on the floor and each other."""
    scene = bpy.context.scene
    active = [o for o in util.roots(util.subjects(objects)) if o.type == "MESH"]
    if not active:
        raise ValueError("Name at least one mesh object to drop.")
    _, _, _, radius = util.bounds(active)
    passive = _colliders(active)
    ground = None
    if not bpy.data.collections.get(util.BACKDROP) or not bpy.data.collections[util.BACKDROP].objects:
        ground = _temporary_ground(active)
        passive.append(ground)

    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    if world.collection is None:
        world.collection = bpy.data.collections.new("Studio Physics")
    util.set_if(world, "substeps_per_frame", 20)
    util.set_if(world, "solver_iterations", 20)
    first = util.to_frame(start_seconds)
    last = util.to_frame(start_seconds + seconds)
    world.point_cache.frame_start, world.point_cache.frame_end = first, last

    def enrol(obj, kind):
        if obj.name not in world.collection.objects:
            world.collection.objects.link(obj)
        if obj.rigid_body is None:
            with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
                bpy.ops.rigidbody.object_add()
        body = obj.rigid_body
        body.type = kind
        body.collision_shape = "CONVEX_HULL" if kind == "ACTIVE" else "MESH"
        body.restitution, body.friction = bounciness, friction
        body.use_margin = True
        # The default margin is 4 cm, which makes small objects hover; scale it to the scene.
        body.collision_margin = min(0.04, radius * 0.004)
        if kind == "ACTIVE":
            body.linear_damping, body.angular_damping = 0.1, 0.25

    for obj in active:
        enrol(obj, "ACTIVE")
    for obj in passive:
        enrol(obj, "PASSIVE")

    path = {obj.name: [] for obj in active}
    for frame in range(first, last + 1):
        scene.frame_set(frame)
        for obj in active:
            path[obj.name].append(obj.matrix_world.copy())

    for obj in active + passive:
        if obj.name in world.collection.objects:
            world.collection.objects.unlink(obj)
    bpy.ops.rigidbody.world_remove()
    if ground is not None:
        mesh = ground.data
        bpy.data.objects.remove(ground, do_unlink=True)
        bpy.data.meshes.remove(mesh)

    resting = {}
    for obj in active:
        obj.rotation_mode = "XYZ"
        previous = obj.rotation_euler.copy()
        scale = obj.scale.copy()
        for offset, matrix in enumerate(path[obj.name]):
            location, rotation, _ = matrix.decompose()
            previous = rotation.to_euler("XYZ", previous)
            obj.location, obj.rotation_euler, obj.scale = location, previous, scale
            if keep_animation:
                obj.keyframe_insert("location", frame=first + offset)
                obj.keyframe_insert("rotation_euler", frame=first + offset)
        resting[obj.name] = util.rounded(obj.location)
    if keep_animation:
        util.extend_timeline(last)
    scene.frame_set(last if keep_animation else scene.frame_current)
    bpy.context.view_layer.update()
    return {"dropped": list(resting), "resting_at": resting, "animated": bool(keep_animation),
            "seconds": seconds, "tip": "Objects must start above where they should land, not overlapping."}


@command()
def drape_cloth(over=None, name="Cloth", size=None, color="#b9c4d6", drop_height=None, seconds=2.5):
    """Drop a sheet of fabric onto objects and keep the folded result as an ordinary object."""
    from .materials import build_material
    scene = bpy.context.scene
    targets = [o for o in util.require_subjects(over) if o.type == "MESH"]
    lo, hi, center, radius = util.bounds(targets)
    width = float(size) if size else max(hi.x - lo.x, hi.y - lo.y) * 1.9
    colliders = targets + [o for o in _colliders(targets) if o not in targets]
    ground = None
    if not bpy.data.collections.get(util.BACKDROP) or not bpy.data.collections[util.BACKDROP].objects:
        ground = _temporary_ground(targets)
        colliders.append(ground)

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=56, y_segments=56, size=width / 2)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    cloth = bpy.data.objects.new(name, mesh)
    cloth.location = (center.x, center.y, hi.z + (drop_height if drop_height is not None else radius * 0.15))
    scene.collection.objects.link(cloth)

    sim = cloth.modifiers.new("Cloth", "CLOTH")
    util.set_if(sim.settings, "quality", 8)
    util.set_if(sim.settings, "mass", 0.25)
    util.set_if(sim.settings, "bending_stiffness", 0.4)
    sim.collision_settings.use_collision = True
    sim.collision_settings.distance_min = max(radius * 0.012, 0.0015)
    sim.collision_settings.collision_quality = 4
    sim.collision_settings.use_self_collision = False
    frames = max(10, int(seconds * util.fps()))
    sim.point_cache.frame_start, sim.point_cache.frame_end = 1, frames + 1
    added = []
    for obj in colliders:
        if not any(m.type == "COLLISION" for m in obj.modifiers):
            added.append((obj, obj.modifiers.new("Studio Collision", "COLLISION")))
        obj.collision.thickness_outer = max(radius * 0.01, 0.001)
        obj.collision.cloth_friction = 12
    current = scene.frame_current
    for frame in range(1, frames + 2):
        scene.frame_set(frame)
    freeze(cloth)
    scene.frame_set(current)
    for obj, mod in added:
        obj.modifiers.remove(mod)
    if ground is not None:
        ground_mesh = ground.data
        bpy.data.objects.remove(ground, do_unlink=True)
        bpy.data.meshes.remove(ground_mesh)

    for poly in cloth.data.polygons:
        poly.use_smooth = True
    thickness = cloth.modifiers.new("Studio Thickness", "SOLIDIFY")
    thickness.thickness = max(width * 0.004, 0.0008)
    soften = cloth.modifiers.new("Studio Soften", "SUBSURF")
    soften.levels = soften.render_levels = 1
    material, _ = build_material(f"{name} fabric", "fabric", color, width, width)
    cloth.data.materials.append(material)
    bpy.context.view_layer.update()
    return {"name": cloth.name, "size": util.rounded(cloth.dimensions), "draped_over": [o.name for o in targets]}
