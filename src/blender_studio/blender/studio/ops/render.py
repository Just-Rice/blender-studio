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


def _has_glass(scene):
    """True when something visible is see-through (glass, water, clear liquid)."""
    for obj in scene.objects:
        if obj.type != "MESH" or obj.hide_render:
            continue
        for slot in obj.material_slots:
            tree = slot.material.node_tree if slot.material and slot.material.use_nodes else None
            for node in tree.nodes if tree else ():
                socket = node.inputs.get("Transmission Weight") if node.type == "BSDF_PRINCIPLED" else None
                if (socket is not None and socket.default_value > 0.5) or node.type in ("BSDF_GLASS",
                                                                                      "BSDF_REFRACTION"):
                    return True
    return False


# EEVEE cannot see through one glass surface into another, so a bottle of liquid previews as a dark
# solid. Previews of scenes with glass use Cycles at a few samples instead, which shows it truly.
GLASS_PREVIEW_SAMPLES = {"draft": 16, "preview": 48}


def _write(scene, path):
    settings = scene.render.image_settings
    util.set_if(settings, "media_type", "IMAGE")
    settings.file_format = "PNG"
    settings.color_mode = "RGBA" if scene.render.film_transparent else "RGB"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def _ensure_camera(scene):
    """With no camera yet, frame one on the whole scene instead of failing, and say so."""
    if scene.camera is not None:
        return {}
    from .camera import frame_camera
    frame_camera()
    return {"note": "There was no camera, so one was framed on the whole scene. Use frame_camera to change it."}


@command(mutates=False)
def render(quality="preview", path=None, engine=None, samples=None, transparent=False, at_seconds=None):
    quality = quality.lower()
    if quality not in QUALITY:
        raise ValueError(f"Unknown quality '{quality}'. Choose from: {', '.join(QUALITY)}")
    scene = bpy.context.scene
    note = _ensure_camera(scene)
    spec = QUALITY[quality]
    engine, samples = (engine or spec["engine"]).lower(), samples or spec["samples"]
    if engine == "eevee" and quality in GLASS_PREVIEW_SAMPLES and _has_glass(scene):
        engine, samples = "cycles", GLASS_PREVIEW_SAMPLES[quality]
        note = {"note": " ".join(filter(None, [note.get("note"), "Glass in the scene, so this preview used the "
                                               "realistic renderer to show it truly."]))}
    used = _configure(scene, engine, samples)
    scene.render.resolution_percentage = spec["percent"]
    scene.render.film_transparent = bool(transparent)
    path = path or state.render_path(quality)
    if at_seconds is not None:
        scene.frame_set(util.to_frame(at_seconds))
    try:
        try:
            _write(scene, path)
        except RuntimeError as error:
            # A heavy scene can exhaust the graphics card's memory; the CPU is slower but has more.
            if scene.render.engine != "CYCLES" or scene.cycles.device != "GPU" or "emory" not in str(error):
                raise
            scene.cycles.device = "CPU"
            _write(scene, path)
            used = "Cycles on CPU"
            note = {"note": " ".join(filter(None, [note.get("note"), "The graphics card ran out of memory, so this "
                                                   "render used the CPU instead."]))}
    finally:
        scene.render.resolution_percentage = 100
    return {"path": path, "engine": used, "quality": quality,
            "size": [scene.render.resolution_x * spec["percent"] // 100,
                     scene.render.resolution_y * spec["percent"] // 100], **note}


@command(mutates=False)
def contact_sheet(subjects=None):
    """Render the subject from five fixed angles with flat studio shading, to check its shape."""
    scene = bpy.context.scene
    targets = util.require_subjects(subjects)
    _, _, center, _ = util.bounds(targets)
    corners = util.shape_points(targets)
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


@command(mutates=False)
def render_animation(path=None, quality="draft", seconds=None, start_seconds=0.0, strip_frames=6):
    """Render the timeline to an MP4 video, plus a few still frames so the motion can be checked."""
    quality = quality.lower()
    if quality not in QUALITY:
        raise ValueError(f"Unknown quality '{quality}'. Choose from: {', '.join(QUALITY)}")
    scene = bpy.context.scene
    if not scene.get("studio_animated") or scene.frame_end <= 1:
        raise ValueError("Nothing is animated yet. Use animate, animate_character, drop_objects or play_animation.")
    note = _ensure_camera(scene)
    spec = QUALITY[quality]
    first = util.to_frame(start_seconds)
    last = util.to_frame(start_seconds + seconds) if seconds else scene.frame_end
    last = max(first + 1, min(last, scene.frame_end))
    used = _configure(scene, spec["engine"], min(spec["samples"], 32 if spec["engine"] == "eevee" else 96))
    render, settings = scene.render, scene.render.image_settings
    saved = (scene.frame_start, scene.frame_end, scene.frame_current, render.resolution_x, render.resolution_y,
             render.resolution_percentage, render.filepath, render.film_transparent)
    path = path or state.render_path("video", "mp4")
    stills = []
    try:
        # H.264 needs even dimensions, so bake the scale into the size.
        render.resolution_x = int(saved[3] * spec["percent"] / 100) // 2 * 2
        render.resolution_y = int(saved[4] * spec["percent"] / 100) // 2 * 2
        render.resolution_percentage = 100
        render.film_transparent = False
        scene.frame_start, scene.frame_end = first, last
        util.set_if(settings, "media_type", "VIDEO")
        settings.file_format = "FFMPEG"
        render.ffmpeg.format, render.ffmpeg.codec = "MPEG4", "H264"
        render.ffmpeg.constant_rate_factor = "HIGH"
        render.ffmpeg.ffmpeg_preset = "GOOD"
        render.ffmpeg.audio_codec = "NONE"
        render.filepath = path
        bpy.ops.render.render(animation=True)
        count = max(2, min(int(strip_frames), 12))
        for index in range(count):
            frame = first + round((last - first) * index / (count - 1))
            scene.frame_set(frame)
            still = state.render_path(f"strip-{index:02d}")
            _write(scene, still)
            stills.append({"seconds": round((frame - 1) / util.fps(), 2), "path": still})
    finally:
        (scene.frame_start, scene.frame_end, frame_current, render.resolution_x, render.resolution_y,
         render.resolution_percentage, render.filepath, render.film_transparent) = saved
        scene.frame_set(frame_current)
    return {"path": path, "engine": used, "seconds": round((last - first + 1) / util.fps(), 2),
            "frames": last - first + 1, "fps": round(util.fps(), 2), "stills": stills, **note}
