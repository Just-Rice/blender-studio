"""Organic shapes without brush strokes: rocks, terrain, blobs, limbs, surface roughening and cuts."""
import random

import bmesh
import bpy
from mathutils import Vector, noise

from .. import util
from ..commands import command

BOOLEANS = {"difference": "DIFFERENCE", "union": "UNION", "intersect": "INTERSECT"}


def _new_object(name, bm, smooth=True):
    for face in bm.faces:
        face.smooth = smooth
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def freeze(obj, only=None):
    """Bake modifiers into the mesh. With `only`, bake just that modifier and keep the rest."""
    hidden = []
    if only is not None:
        for mod in obj.modifiers:
            if mod != only and mod.show_viewport:
                mod.show_viewport = False
                hidden.append(mod)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    baked = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    for mod in hidden:
        mod.show_viewport = True
    old = obj.data
    if obj.type == "MESH":
        baked.name = old.name
        obj.data = baked
        if only is not None:
            obj.modifiers.remove(only)
        else:
            obj.modifiers.clear()
        if old.users == 0:
            bpy.data.meshes.remove(old)
        return obj
    # Metaballs and curves cannot hold a mesh, so swap in a new mesh object.
    replacement = bpy.data.objects.new(obj.name + " mesh", baked)
    replacement.matrix_world = obj.matrix_world
    bpy.context.scene.collection.objects.link(replacement)
    name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    replacement.name = name
    return replacement


def _describe(obj):
    return {"name": obj.name, "location": util.rounded(obj.location), "size": util.rounded(obj.dimensions),
            "faces": len(obj.data.polygons)}


@command()
def create_rock(name=None, size=1.0, roughness=0.35, style="smooth", seed=0, location=None):
    """A natural rock about `size` metres across, sitting with its flat base at `location`."""
    rng = random.Random(seed)
    offset = Vector((rng.uniform(0, 100), rng.uniform(0, 100), rng.uniform(0, 100)))
    lowpoly = style == "lowpoly"
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2 if lowpoly else 5, radius=0.5)
    squash = Vector((rng.uniform(0.85, 1.2), rng.uniform(0.8, 1.15), rng.uniform(0.55, 0.85)))
    for vert in bm.verts:
        direction = vert.co.normalized()
        lumps = noise.noise(direction * 1.1 + offset)
        grit = 0.0 if lowpoly else noise.fractal(direction * 3.0 + offset, 1.0, 2.0, 4)
        vert.co += direction * (lumps * roughness * 0.45 + grit * roughness * 0.12)
        vert.co = Vector((vert.co.x * squash.x, vert.co.y * squash.y, vert.co.z * squash.z)) * size
    floor = min(v.co.z for v in bm.verts) * 0.72
    for vert in bm.verts:
        vert.co.z = max(vert.co.z, floor) - floor
    obj = _new_object(name or "Rock", bm, smooth=not lowpoly)
    obj.location = location or (0, 0, 0)
    obj.rotation_euler.z = rng.uniform(0, 6.283)
    bpy.context.view_layer.update()
    return _describe(obj)


@command()
def create_terrain(name=None, size=10.0, height=1.5, detail=1.0, style="smooth", island=False, seed=0,
                   location=None):
    """Rolling ground `size` metres wide with hills up to `height`. island=True slopes the edges down to zero."""
    rng = random.Random(seed)
    offset = Vector((rng.uniform(0, 100), rng.uniform(0, 100), 0))
    lowpoly = style == "lowpoly"
    segments = 30 if lowpoly else 160
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=segments, y_segments=segments, size=size / 2)
    frequency = detail * 3.0 / size
    for vert in bm.verts:
        point = Vector((vert.co.x, vert.co.y, 0)) * frequency + offset
        level = 0.5 + 0.5 * noise.fractal(point, 1.0, 2.0, 2 if lowpoly else 6)
        if island:
            edge = min(1.0, (Vector((vert.co.x, vert.co.y)).length / (size / 2)) ** 2)
            level = (level * 0.8 + 0.2) * max(0.0, 1.0 - edge) ** 0.8
        vert.co.z = max(level, 0.0) * height
    if island:
        # Trim the square sheet to the round shoreline.
        outside = [v for v in bm.verts if Vector((v.co.x, v.co.y)).length > size / 2]
        bmesh.ops.delete(bm, geom=outside, context="VERTS")
    if lowpoly:
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
    obj = _new_object(name or "Terrain", bm, smooth=not lowpoly)
    obj.location = location or (0, 0, 0)
    bpy.context.view_layer.update()
    return _describe(obj)


@command()
def create_blob(balls, name=None, location=None):
    """Soft organic form from spheres that melt together where they overlap. balls is [[x, y, z, radius], ...]."""
    if not balls:
        raise ValueError("Give at least one ball as [x, y, z, radius].")
    data = bpy.data.metaballs.new("StudioBlobTemp")
    smallest = min(float(ball[3]) for ball in balls)
    data.resolution = data.render_resolution = max(smallest * 0.14, 1e-4)
    data.threshold = 0.6
    for x, y, z, radius in balls:
        element = data.elements.new()
        element.co = (x, y, z)
        # A metaball's visible surface sits inside its radius; enlarge so the stated radius is what you see.
        element.radius = float(radius) * 1.9
    holder = bpy.data.objects.new("StudioBlobTemp", data)
    bpy.context.scene.collection.objects.link(holder)
    obj = freeze(holder)
    bpy.data.metaballs.remove(data)
    obj.name = name or "Blob"
    obj.data.name = obj.name
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.location = location or (0, 0, 0)
    bpy.context.view_layer.update()
    return _describe(obj)


@command()
def create_limbs(joints, links, name=None, smoothness=2, location=None):
    """A smooth skin wrapped around a stick skeleton: bodies, necks, tails, branches, tentacles.
    joints is {"hip": [x, y, z, radius], ...}; links is [["hip", "chest"], ...]."""
    names = list(joints)
    missing = [end for link in links for end in link if end not in joints]
    if missing:
        raise ValueError(f"Links mention joints that are not defined: {', '.join(sorted(set(missing)))}")
    mesh = bpy.data.meshes.new(name or "Limbs")
    mesh.from_pydata([tuple(joints[j][:3]) for j in names], [(names.index(a), names.index(b)) for a, b in links], [])
    obj = bpy.data.objects.new(name or "Limbs", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Skin", "SKIN")
    points = [joints[j][:3] for j in names]
    span = max(max(p[i] for p in points) - min(p[i] for p in points) for i in range(3))
    # With no thickness given, stay slender relative to the skeleton rather than assuming a size in metres.
    slender = max(span * 0.06, 1e-4)
    for index, joint in enumerate(names):
        radius = float(joints[joint][3]) if len(joints[joint]) > 3 else slender
        mesh.skin_vertices[0].data[index].radius = (radius, radius)
        mesh.skin_vertices[0].data[index].use_root = index == 0
    if smoothness:
        smooth = obj.modifiers.new("Smooth", "SUBSURF")
        smooth.levels = smooth.render_levels = int(smoothness)
    freeze(obj)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.location = location or (0, 0, 0)
    bpy.context.view_layer.update()
    return _describe(obj)


@command()
def sculpt(objects, roughness=0.0, detail=1.0, smooth=0, remesh=0.0, subdivide=0):
    """Reshape existing meshes. Each call replaces the previous sculpt settings on those objects."""
    done = []
    for obj in util.subjects(objects):
        if obj.type != "MESH":
            continue
        for mod in [m for m in obj.modifiers if m.name.startswith("Studio Sculpt")]:
            obj.modifiers.remove(mod)
        local = max((max(c[i] for c in obj.bound_box) - min(c[i] for c in obj.bound_box)) for i in range(3)) or 1.0
        if subdivide:
            mod = obj.modifiers.new("Studio Sculpt Subdivide", "SUBSURF")
            mod.levels = mod.render_levels = int(subdivide)
        if remesh:
            mod = obj.modifiers.new("Studio Sculpt Remesh", "REMESH")
            mod.mode = "VOXEL"
            mod.voxel_size = max(float(remesh), 0.004) * local
            mod.use_smooth_shade = True
        if roughness:
            if not subdivide and not remesh and len(obj.data.vertices) < 3000:
                # Displacement needs points to move; add them without changing the shape.
                mod = obj.modifiers.new("Studio Sculpt Density", "SUBSURF")
                mod.subdivision_type = "SIMPLE"
                mod.levels = mod.render_levels = 5 if len(obj.data.vertices) < 100 else 3
            texture = bpy.data.textures.new(f"{obj.name} sculpt", "CLOUDS")
            texture.noise_scale = local * 0.3 / max(detail, 0.05)
            texture.noise_depth = 3
            mod = obj.modifiers.new("Studio Sculpt Displace", "DISPLACE")
            mod.texture = texture
            mod.texture_coords = "LOCAL"
            mod.strength = float(roughness) * local
            mod.mid_level = 0.5
        if smooth:
            mod = obj.modifiers.new("Studio Sculpt Smooth", "SMOOTH")
            mod.factor = 0.5
            mod.iterations = int(smooth) * 4
        if roughness or smooth or remesh:
            for poly in obj.data.polygons:
                poly.use_smooth = True
        done.append(obj.name)
    if not done:
        raise ValueError("No mesh objects to sculpt.")
    bpy.context.view_layer.update()
    return {"sculpted": done, "roughness": roughness, "detail": detail, "smooth": smooth, "remesh": remesh,
            "subdivide": subdivide}


@command()
def boolean(target, cutter, operation="difference", keep_cutter=False):
    """Cut `cutter` out of `target` (difference), fuse them (union), or keep only the overlap (intersect)."""
    operation = operation.lower()
    if operation not in BOOLEANS:
        raise ValueError(f"Unknown operation '{operation}'. Choose from: {', '.join(BOOLEANS)}")
    base, tool = util.get_object(target), util.get_object(cutter)
    if base.type != "MESH" or tool.type != "MESH":
        raise ValueError("Both objects must be meshes.")
    before = len(base.data.polygons)
    mod = base.modifiers.new("Studio Boolean", "BOOLEAN")
    mod.object = tool
    mod.operation = BOOLEANS[operation]
    mod.solver = "EXACT"
    base.modifiers.move(len(base.modifiers) - 1, 0)
    freeze(base, only=mod)
    if keep_cutter:
        tool.hide_render = tool.hide_viewport = True
    else:
        bpy.data.objects.remove(tool, do_unlink=True)
    bpy.context.view_layer.update()
    result = _describe(base)
    if len(base.data.polygons) == before:
        result["warning"] = "The shape did not change. Check that the two objects actually overlap."
    return result
