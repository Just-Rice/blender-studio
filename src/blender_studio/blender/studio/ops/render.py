"""Rendering: quick previews, final images, and a multi-angle sheet for spotting mistakes."""
import bpy

from .. import state, util
from ..commands import command
from .camera import direction, frame, make_camera

QUALITY = {
    "draft": dict(engine="eevee", samples=16, percent=50),
    "preview": dict(engine="eevee", samples=64, percent=100),
    "final": dict(engine="cycles", samples=256, percent=100),
}
SHEET_VIEWS = (("front", 0, 6), ("right", 90, 6), ("back", 180, 6), ("top", 0, 89), ("three-quarter", 35, 25))


def _eevee_id():
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            bpy.context.scene.render.engine = engine
            return engine
        except TypeError:
            continue


def _use_gpu(scene):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA", "METAL", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = backend
            except TypeError:
                continue
            prefs.get_devices()
            devices = [d for d in prefs.devices if d.type == backend]
            if devices:
                for device in prefs.devices:
                    device.use = True
                scene.cycles.device = "GPU"
                return backend
        prefs.compute_device_type = "NONE"
    except Exception:
        pass
    scene.cycles.device = "CPU"
    return "CPU"


def _configure(scene, engine, samples):
    if engine == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        return f"Cycles on {_use_gpu(scene)}"
    _eevee_id()
    eevee = scene.eevee
    util.set_if(eevee, "taa_render_samples", samples)
    util.set_if(eevee, "use_raytracing", True)
    util.set_if(eevee, "use_shadows", True)
    util.set_if(eevee, "use_fast_gi", True)
    util.set_if(eevee, "shadow_ray_count", 3)
    util.set_if(eevee, "shadow_step_count", 8)
    # Blender's defaults assume room-sized scenes; scale the tracing distances to this one or small
    # objects get smeared reflections and large ones lose contact shadows.
    _, _, _, radius = util.bounds(util.subjects())
    options = getattr(eevee, "ray_tracing_options", None)
    if options is not None:
        util.set_if(options, "resolution_scale", "1")
        util.set_if(options, "screen_trace_quality", 1.0)
        util.set_if(options, "screen_trace_thickness", radius * 0.05)
    util.set_if(eevee, "fast_gi_thickness_near", radius * 0.15)
    return "EEVEE"


def _write(scene, path):
    settings = scene.render.image_settings
    util.set_if(settings, "media_type", "IMAGE")
    settings.file_format = "PNG"
    settings.color_mode = "RGBA" if scene.render.film_transparent else "RGB"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


@command(mutates=False)
def render(quality="preview", path=None, engine=None, samples=None, transparent=False):
    quality = quality.lower()
    if quality not in QUALITY:
        raise ValueError(f"Unknown quality '{quality}'. Choose from: {', '.join(QUALITY)}")
    scene = bpy.context.scene
    if scene.camera is None:
        raise ValueError("There is no camera yet. Call frame_camera first.")
    spec = QUALITY[quality]
    used = _configure(scene, (engine or spec["engine"]).lower(), samples or spec["samples"])
    scene.render.resolution_percentage = spec["percent"]
    scene.render.film_transparent = bool(transparent)
    path = path or state.render_path(quality)
    try:
        _write(scene, path)
    finally:
        scene.render.resolution_percentage = 100
    return {"path": path, "engine": used, "quality": quality,
            "size": [scene.render.resolution_x * spec["percent"] // 100,
                     scene.render.resolution_y * spec["percent"] // 100]}


@command(mutates=False)
def contact_sheet(subjects=None):
    """Render the subject from five fixed angles with flat studio shading, to check its shape."""
    scene = bpy.context.scene
    targets = util.require_subjects(subjects)
    _, _, center, _ = util.bounds(targets)
    corners = util.bbox_corners(targets)
    saved = (scene.camera, scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
             scene.render.film_transparent)
    cam = make_camera("Studio Sheet Camera")
    shots = []
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
        shading = scene.display.shading
        shading.light, shading.color_type = "STUDIO", "MATERIAL"
        shading.show_shadows = shading.show_cavity = True
        scene.render.resolution_x, scene.render.resolution_y = 640, 480
        scene.render.film_transparent = False
        scene.camera = cam
        for label, az, el in SHEET_VIEWS:
            frame(cam, corners, center, direction(az, el), 0.8)
            path = state.render_path(f"sheet-{label}")
            _write(scene, path)
            shots.append({"label": label, "path": path})
    finally:
        (scene.camera, scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
         scene.render.film_transparent) = saved
        data = cam.data
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(data)
    return {"views": shots}
