"""Camera placement that frames the subject automatically."""
import math

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from .. import util
from ..commands import command

SHOTS = {
    "three_quarter": dict(az=32, el=18, focal=60, about="Angled hero view showing front, side and top. Best default."),
    "front": dict(az=0, el=4, focal=70, about="Straight-on, flat and graphic."),
    "side": dict(az=90, el=4, focal=70, about="Profile view from the right."),
    "back": dict(az=180, el=10, focal=60, about="From behind."),
    "top": dict(az=0, el=88, focal=50, about="Looking straight down. Flat-lay."),
    "low_hero": dict(az=28, el=-4, focal=28, about="Low wide angle looking up. Makes the subject feel big."),
    "closeup": dict(az=25, el=14, focal=100, fill=1.15, about="Tight telephoto detail; crops into the subject."),
    "wide": dict(az=38, el=24, focal=24, fill=0.5, about="Pulled back to show the surroundings."),
    "isometric": dict(az=45, el=35.264, focal=50, ortho=True, about="No perspective. Game-art and diagram look."),
}
ASPECTS = {"16:9": (1920, 1080), "3:2": (1620, 1080), "4:3": (1440, 1080), "1:1": (1200, 1200),
           "4:5": (1080, 1350), "9:16": (1080, 1920), "21:9": (2100, 900)}


def direction(azimuth_deg, elevation_deg):
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    return Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


def frame(cam, corners, center, direction_vec, fill):
    """Move cam along direction_vec until the corners fill `fill` of the frame, centred."""
    scene = bpy.context.scene
    look = -direction_vec
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    radius = max((c - center).length for c in corners) or 1.0
    target = Vector(center)
    distance = radius * 4
    for _ in range(8):
        cam.location = target + direction_vec * distance
        if cam.data.type == "ORTHO":
            cam.data.ortho_scale = max(cam.data.ortho_scale, 1e-3)
        bpy.context.view_layer.update()
        ndc = [world_to_camera_view(scene, cam, c) for c in corners]
        xs, ys = [p.x for p in ndc], [p.y for p in ndc]
        extent = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
        # Re-centre on the projected middle of the subject, then correct the size.
        right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
        up = cam.matrix_world.to_3x3() @ Vector((0, 1, 0))
        frame_pts = cam.data.view_frame(scene=scene)
        width = abs(frame_pts[0].x - frame_pts[2].x)
        height = abs(frame_pts[0].y - frame_pts[2].y)
        depth = abs(frame_pts[0].z) or 1.0
        span = distance / depth if cam.data.type != "ORTHO" else 1.0
        target += right * ((min(xs) + max(xs)) / 2 - 0.5) * width * span
        target += up * ((min(ys) + max(ys)) / 2 - 0.5) * height * span
        if cam.data.type == "ORTHO":
            cam.data.ortho_scale *= extent / fill
        else:
            distance = max(distance * extent / fill, radius * 0.05)
    cam.location = target + direction_vec * distance
    bpy.context.view_layer.update()
    return distance, target


def make_camera(name):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    util.link_only(obj, util.CAMERAS)
    return obj


@command()
def frame_camera(shot="three_quarter", subjects=None, focal_length=None, azimuth_deg=None, elevation_deg=None,
                 fill=None, depth_of_field=None, aspect=None):
    shot = shot.lower()
    if shot not in SHOTS:
        raise ValueError(f"Unknown shot '{shot}'. Choose from: {', '.join(SHOTS)}")
    scene = bpy.context.scene
    if aspect:
        if aspect not in ASPECTS:
            raise ValueError(f"Unknown aspect '{aspect}'. Choose from: {', '.join(ASPECTS)}")
        scene.render.resolution_x, scene.render.resolution_y = ASPECTS[aspect]
    spec = SHOTS[shot]
    targets = util.require_subjects(subjects)
    _, _, center, radius = util.bounds(targets)

    cam = bpy.data.objects.get("Studio Camera")
    if cam is None or cam.type != "CAMERA":
        cam = make_camera("Studio Camera")
    cam.data.type = "ORTHO" if spec.get("ortho") else "PERSP"
    cam.data.lens = focal_length or spec["focal"]
    cam.data.clip_start, cam.data.clip_end = radius * 0.01, radius * 400
    scene.camera = cam

    az = spec["az"] if azimuth_deg is None else azimuth_deg
    el = spec["el"] if elevation_deg is None else elevation_deg
    fill = fill or spec.get("fill", 0.78)
    distance, target = frame(cam, util.shape_points(targets), center, direction(az, el), fill)

    dof = cam.data.dof
    dof.use_dof = bool(depth_of_field)
    if depth_of_field:
        dof.focus_distance = distance
        # Blur depends on distance, so rescale the f-stop to give the same look a full-frame camera
        # would give a subject two metres away, whatever the size of the scene.
        dof.aperture_fstop = min(max(float(depth_of_field) * 2.0 / distance, 0.1), 128.0)
    return {
        "shot": shot, "focal_length_mm": cam.data.lens, "azimuth_deg": az, "elevation_deg": el,
        "distance": round(distance, 3), "looking_at": util.rounded(target),
        "depth_of_field_fstop": depth_of_field or "off",
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
    }
