"""Blender Studio MCP server: tools that let any AI model make good-looking 3D art in Blender."""
import atexit
import io
import json
import subprocess
from pathlib import Path
from typing import Literal, Optional, Union

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage
from PIL import ImageDraw

from .launcher import Blender, BlenderError, find_blender

GUIDE = (Path(__file__).parent / "guide.md").read_text(encoding="utf-8")
INSTRUCTIONS = """Blender Studio drives a real copy of Blender. It starts by itself on the first tool call.

Work like a photographer, in this order:
1. Build the subject (create_object, import_asset, run_python for custom shapes).
2. apply_material, add_polish, add_backdrop.
3. studio_lighting, frame_camera, set_look.
4. scene_check, then render_preview and LOOK at the picture. Fix what is wrong and render again.
5. Only when the preview looks right: render_final.

Beyond basic shapes there are tools for organic forms (create_rock, create_terrain, create_blob, create_limbs,
sculpt, boolean), people (create_character, create_human, pose_character), and motion (animate,
animate_character, drop_objects, drape_cloth, render_animation for video).

The staging tools are a fast route to a solid result, not a rulebook: if your own lights, shapes or
materials in run_python would look better, use them. Spend your effort on the subject's detail.

Never finish without looking at a render. design_guide has optional craft tips.
Units are metres, Z is up, the front of the scene faces -Y. Every change can be reversed with undo."""

Names = Optional[Union[str, list[str]]]
Color = Optional[Union[str, list[float]]]

mcp = FastMCP("blender-studio", instructions=INSTRUCTIONS)
blender = Blender()
atexit.register(blender.close)


def call(cmd, **args):
    try:
        return blender.call(cmd, **args)
    except BlenderError as exc:
        raise ValueError(str(exc)) from None


def _jpeg(image, longest=1280):
    image = image.convert("RGB")
    image.thumbnail((longest, longest))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88)
    return Image(data=buffer.getvalue(), format="jpeg")


def _exposure_notes(image):
    """Plain-language warnings about brightness, so obvious exposure faults are never missed."""
    grey = image.convert("L").resize((160, 100))
    pixels = grey.tobytes()
    mean = sum(pixels) / len(pixels)
    dark = sum(p < 12 for p in pixels) / len(pixels)
    blown = sum(p > 250 for p in pixels) / len(pixels)
    notes = []
    if mean < 40:
        notes.append("The image is very dark overall; raise studio_lighting strength or set_look exposure.")
    if dark > 0.6 and mean >= 40:
        notes.append("Over half the frame is pure black.")
    if blown > 0.12:
        notes.append(f"{blown:.0%} of the image is blown out to white; lower the lighting strength or exposure.")
    if max(pixels) - min(pixels) < 50:
        notes.append("Very little contrast; the image looks flat.")
    return notes


# --- scene -----------------------------------------------------------------

@mcp.tool()
def design_guide() -> str:
    """Read this once before making a scene: the short craft rules for lighting, composition, colour and finish."""
    return GUIDE


@mcp.tool()
def list_presets() -> dict:
    """List every material, lighting style, backdrop, camera shot and look preset with a one-line description."""
    return call("list_presets")


@mcp.tool()
def scene_info() -> dict:
    """Describe the current scene: objects with position and size, lights, camera, overall bounds."""
    return call("scene_info")


@mcp.tool()
def new_scene() -> dict:
    """Start over with an empty scene."""
    return call("new_scene")


@mcp.tool()
def create_object(
    kind: Literal["cube", "sphere", "ico_sphere", "cylinder", "cone", "torus", "plane", "monkey", "text"],
    name: Optional[str] = None,
    location: Optional[list[float]] = None,
    rotation_deg: Optional[list[float]] = None,
    scale: Optional[Union[float, list[float]]] = None,
    text: Optional[str] = None,
) -> dict:
    """Add a basic shape. Each is about 2 m across before scaling (unit radius), centred on its location.
    scale may be one number or [x, y, z]. For kind='text', pass the words in `text`; it stands upright facing front."""
    return call("create_object", kind=kind, name=name, location=location, rotation_deg=rotation_deg,
                scale=scale, text=text)


@mcp.tool()
def transform_object(
    name: str,
    location: Optional[list[float]] = None,
    rotation_deg: Optional[list[float]] = None,
    scale: Optional[Union[float, list[float]]] = None,
) -> dict:
    """Move, rotate or resize an object. Only the values you pass are changed."""
    return call("transform_object", name=name, location=location, rotation_deg=rotation_deg, scale=scale)


@mcp.tool()
def delete_objects(names: Union[str, list[str]]) -> dict:
    """Delete one or more objects by name."""
    return call("delete_objects", names=names)


@mcp.tool()
def run_python(code: str) -> dict:
    """Run Python inside Blender for anything the other tools cannot do (custom meshes, modifiers, animation).
    `bpy`, `bmesh`, `mathutils`, `Vector` and `math` are ready to use. Assign to `result` to return a value.
    Prefer the dedicated tools for lighting, materials, camera and rendering; they give better-looking results."""
    return call("run_python", code=code)


@mcp.tool()
def undo(steps: int = 1) -> dict:
    """Step back to how the scene was before the last change (up to 15 changes)."""
    return call("undo", steps=steps)


# --- making it look good ---------------------------------------------------

@mcp.tool()
def apply_material(
    objects: Names = None,
    preset: Optional[str] = None,
    color: Color = None,
    roughness: Optional[float] = None,
    metallic: Optional[float] = None,
    emission_strength: Optional[float] = None,
    assignments: Optional[list[dict]] = None,
) -> dict:
    """Give objects a realistic surface from a preset (see list_presets: ceramic, plastic_glossy, gold, glass,
    wood, fabric, glow and more). color is '#rrggbb'; leave it out for the natural colour.
    To set many at once, pass assignments=[{"objects": [...], "preset": "...", "color": "..."}, ...]
    instead; each entry takes the same fields."""
    jobs = assignments or [dict(objects=objects, preset=preset, color=color, roughness=roughness,
                                metallic=metallic, emission_strength=emission_strength)]
    done = []
    for job in jobs:
        if not job.get("objects") or not job.get("preset"):
            raise ValueError("Each material needs both 'objects' and 'preset'.")
        done.append(call("apply_material", **{k: job.get(k) for k in (
            "objects", "preset", "color", "roughness", "metallic", "emission_strength")}))
    return done[0] if len(done) == 1 else {"applied": done}


@mcp.tool()
def add_polish(
    objects: Names = None,
    bevel: float = 0.02,
    bevel_segments: int = 3,
    subdivision: int = 0,
    smooth: bool = True,
) -> dict:
    """Round off hard edges and smooth surfaces so objects catch highlights like real ones do.
    bevel is a fraction of the object's smallest side (0.02 is subtle, 0.1 is chunky and toy-like, 0 is off).
    subdivision 1-2 makes organic shapes rounder. Leave objects empty to polish everything."""
    return call("add_polish", objects=objects, bevel=bevel, bevel_segments=bevel_segments,
                subdivision=subdivision, smooth=smooth)


@mcp.tool()
def add_backdrop(
    style: Literal["cyclorama", "floor", "none"] = "cyclorama",
    color: Color = "#d9d9de",
    roughness: float = 0.6,
    gradient: float = 0.5,
) -> dict:
    """Put the subject on a surface so it has a shadow and a horizon. 'cyclorama' is a seamless studio sweep
    (floor curving up into a wall); 'floor' is a wide flat ground. gradient 0-1 darkens the wall as it
    recedes, which adds depth; 0 keeps it evenly lit."""
    return call("add_backdrop", style=style, color=color, roughness=roughness, gradient=gradient)


@mcp.tool()
def studio_lighting(
    style: Literal["three_point", "softbox", "golden_hour", "overcast", "dramatic", "neon", "hdri"] = "three_point",
    strength: float = 1.0,
    contrast: Literal["soft", "medium", "strong"] = "medium",
    subjects: Names = None,
    hdri: Optional[str] = None,
    hdri_rotation_deg: float = 0.0,
) -> dict:
    """Replace all lighting with a rig sized and aimed at the subject. strength scales brightness;
    contrast sets how deep the shadows are. For 'hdri' pass a Poly Haven id from search_assets.
    Optional: lights you build yourself in run_python work just as well."""
    return call("studio_lighting", style=style, strength=strength, subjects=subjects, hdri=hdri,
                hdri_rotation_deg=hdri_rotation_deg, contrast=contrast)


@mcp.tool()
def frame_camera(
    shot: Literal["three_quarter", "front", "side", "back", "top", "low_hero", "closeup", "wide",
                  "isometric"] = "three_quarter",
    subjects: Names = None,
    focal_length: Optional[float] = None,
    azimuth_deg: Optional[float] = None,
    elevation_deg: Optional[float] = None,
    fill: Optional[float] = None,
    depth_of_field: Optional[float] = None,
    aspect: Optional[Literal["16:9", "3:2", "4:3", "1:1", "4:5", "9:16", "21:9"]] = None,
) -> dict:
    """Place the camera so the subject is centred and fills the frame. azimuth_deg: 0 front, 90 right,
    180 back. elevation_deg: 0 eye level, 90 overhead. fill is the share of the frame the subject takes
    (default 0.78). depth_of_field is an f-stop (1.8 strong blur, 8 slight). subjects limits framing."""
    return call("frame_camera", shot=shot, subjects=subjects, focal_length=focal_length, azimuth_deg=azimuth_deg,
                elevation_deg=elevation_deg, fill=fill, depth_of_field=depth_of_field, aspect=aspect)


@mcp.tool()
def set_look(
    preset: Literal["product_clean", "cinematic", "soft_pastel", "moody", "vivid", "flat_graphic",
                    "black_and_white"] = "product_clean",
    exposure: Optional[float] = None,
    bloom: Optional[float] = None,
) -> dict:
    """Set the overall mood of the picture: contrast, brightness and highlight glow. exposure is in stops
    (+1 is twice as bright). bloom 0-1 adds a soft glow around bright areas."""
    return call("set_look", preset=preset, exposure=exposure, bloom=bloom)


# --- seeing and checking ---------------------------------------------------

@mcp.tool()
def scene_check() -> dict:
    """Look for common mistakes before rendering: no lights, subject out of frame, objects floating or sunk
    into the floor, duplicates, missing materials, harsh edges."""
    return call("scene_check")


def _render(quality, **args):
    result = call("render", quality=quality, **args)
    image = PILImage.open(result["path"])
    notes = _exposure_notes(image)
    summary = {"saved_to": result["path"], "engine": result["engine"], "size": result["size"]}
    if notes:
        summary["exposure_warnings"] = notes
    return [_jpeg(image), json.dumps(summary)]


@mcp.tool()
def render_preview(quality: Literal["draft", "preview"] = "preview", at_seconds: Optional[float] = None) -> list:
    """Render the camera view quickly and return the picture so you can judge it. 'draft' is half size and
    fastest. Look closely at composition, lighting and materials, then fix and render again.
    at_seconds picks a moment of an animation to look at."""
    return _render(quality, at_seconds=at_seconds)


def _sheet(cells, columns, cell_w, cell_h):
    rows = -(-len(cells) // columns)
    sheet = PILImage.new("RGB", (cell_w * columns, cell_h * rows), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(cells):
        x, y = (index % columns) * cell_w, (index // columns) * cell_h
        sheet.paste(PILImage.open(path).convert("RGB").resize((cell_w, cell_h)), (x, y))
        draw.rectangle((x, y, x + 12 + 7 * len(label), y + 22), fill=(0, 0, 0))
        draw.text((x + 6, y + 5), label, fill=(255, 255, 255))
    return sheet


@mcp.tool()
def render_animation(
    quality: Literal["draft", "preview", "final"] = "draft",
    path: Optional[str] = None,
    seconds: Optional[float] = None,
    start_seconds: float = 0.0,
) -> list:
    """Render the animation to an MP4 video file and return a strip of still frames from it so you can check
    the motion. 'draft' is half size and quick; 'preview' is full size; 'final' uses the slow, realistic
    renderer (minutes per second of video). seconds limits the length; by default the whole timeline is rendered."""
    result = call("render_animation", quality=quality, path=path, seconds=seconds, start_seconds=start_seconds)
    first = PILImage.open(result["stills"][0]["path"])
    cell_w = 420
    cell_h = round(cell_w * first.height / first.width)
    strip = _sheet([(f"{s['seconds']}s", s["path"]) for s in result["stills"]], 3, cell_w, cell_h)
    summary = {key: result[key] for key in ("path", "engine", "seconds", "frames", "fps")}
    return [_jpeg(strip, 1280), json.dumps({"video_saved_to": summary.pop("path"), **summary})]


@mcp.tool()
def render_final(path: Optional[str] = None, samples: int = 256, transparent: bool = False) -> list:
    """Render the finished image at full quality with the Cycles path tracer (slower, most realistic) and
    save it as a PNG. path is where to save it; transparent removes the background."""
    return _render("final", path=path, samples=samples, transparent=transparent)


@mcp.tool()
def contact_sheet(subjects: Names = None) -> list:
    """Show the subject from five angles (front, right, back, top, three-quarter) in plain studio shading.
    Use it to check shape, proportions and that parts actually join up, which a single view can hide."""
    views = call("contact_sheet", subjects=subjects)["views"]
    sheet = _sheet([(view["label"], view["path"]) for view in views], 3, 480, 360)
    return [_jpeg(sheet, 1440), "Views: " + ", ".join(view["label"] for view in views)]


# --- organic shapes --------------------------------------------------------

@mcp.tool()
def create_rock(
    name: Optional[str] = None,
    size: float = 1.0,
    roughness: float = 0.35,
    style: Literal["smooth", "lowpoly"] = "smooth",
    seed: int = 0,
    location: Optional[list[float]] = None,
) -> dict:
    """Make a natural-looking rock or boulder about `size` metres across, resting flat on `location`.
    roughness 0.1 is a river pebble, 0.6 is craggy. Each seed gives a different rock."""
    return call("create_rock", name=name, size=size, roughness=roughness, style=style, seed=seed, location=location)


@mcp.tool()
def create_terrain(
    name: Optional[str] = None,
    size: float = 10.0,
    height: float = 1.5,
    detail: float = 1.0,
    style: Literal["smooth", "lowpoly"] = "smooth",
    island: bool = False,
    seed: int = 0,
    location: Optional[list[float]] = None,
) -> dict:
    """Make hilly ground `size` metres wide with hills up to `height` metres. detail above 1 gives more,
    smaller hills. island=True makes the land fall away to zero at the edges. Each seed is a different landscape."""
    return call("create_terrain", name=name, size=size, height=height, detail=detail, style=style, island=island,
                seed=seed, location=location)


@mcp.tool()
def create_blob(balls: list[list[float]], name: Optional[str] = None, location: Optional[list[float]] = None) -> dict:
    """Make one soft organic shape from spheres that melt together where they overlap: clouds, bodies,
    blobby creatures, snowmen, dough. balls is [[x, y, z, radius], ...]; overlap them by a third or more."""
    return call("create_blob", balls=balls, name=name, location=location)


@mcp.tool()
def create_limbs(
    joints: dict[str, list[float]],
    links: list[list[str]],
    name: Optional[str] = None,
    smoothness: int = 2,
    location: Optional[list[float]] = None,
) -> dict:
    """Wrap a smooth skin around a stick skeleton, for creatures, trees, tentacles, handles and pipes.
    joints maps a name to [x, y, z, radius]; links lists which joints connect, e.g. [["hip", "chest"],
    ["chest", "head"]]. Radius sets the thickness at each joint, in metres; leave it out for a slender default
    sized to the skeleton. The first joint is the root."""
    return call("create_limbs", joints=joints, links=links, name=name, smoothness=smoothness, location=location)


@mcp.tool()
def sculpt(
    objects: Union[str, list[str]],
    roughness: float = 0.0,
    detail: float = 1.0,
    smooth: int = 0,
    remesh: float = 0.0,
    subdivide: int = 0,
) -> dict:
    """Reshape existing objects without brush strokes. roughness pushes the surface in and out with natural
    noise (0.05 is a dented, hand-made look; 0.3 is lumpy); detail above 1 makes the lumps smaller.
    smooth 1-5 melts sharp features. remesh (0.02-0.08) fuses overlapping parts into one clean skin;
    smaller is finer. subdivide 1-3 rounds the shape. Calling again replaces the earlier settings."""
    return call("sculpt", objects=objects, roughness=roughness, detail=detail, smooth=smooth, remesh=remesh,
                subdivide=subdivide)


@mcp.tool()
def boolean(
    target: str,
    cutter: str,
    operation: Literal["difference", "union", "intersect"] = "difference",
    keep_cutter: bool = False,
) -> dict:
    """Carve one object with another. 'difference' cuts the cutter's shape out of the target (holes,
    windows, bites, hollows); 'union' fuses them; 'intersect' keeps only where they overlap.
    The cutter is removed afterwards unless keep_cutter is set."""
    return call("boolean", target=target, cutter=cutter, operation=operation, keep_cutter=keep_cutter)


# --- people ----------------------------------------------------------------

@mcp.tool()
def create_character(
    name: str = "Character",
    style: Literal["toy", "lowpoly", "blocky"] = "toy",
    height: float = 1.7,
    skin: str = "#e2b091",
    top: str = "#3f7fd0",
    bottom: str = "#2c3550",
    shoes: str = "#f1eee8",
    hair: Optional[str] = "#3a2a20",
    location: Optional[list[float]] = None,
    facing_deg: float = 0.0,
    pose: str = "stand",
) -> dict:
    """Add a stylised person with working joints: 'toy' (rounded, big head), 'lowpoly' (faceted) or 'blocky'
    (voxel). Feet stand on `location`; facing_deg 0 faces front. hair "none" is bald. Poses: stand, t_pose,
    wave, cheer, walk, run, sit, point, hands_on_hips, think, jump. The name works with transform_object,
    frame_camera and apply_material; parts are named like 'Name Torso'."""
    return call("create_character", name=name, style=style, height=height, skin=skin, top=top, bottom=bottom,
                shoes=shoes, hair=hair or "none", location=location, facing_deg=facing_deg, pose=pose)


@mcp.tool()
def create_human(
    name: str = "Human",
    gender: Literal["female", "neutral", "male"] = "neutral",
    age: Literal["young", "adult", "elder"] = "adult",
    muscle: float = 0.5,
    weight: float = 0.5,
    height: float = 1.7,
    skin: str = "#c98f6b",
    top: str = "#3f6fa8",
    bottom: str = "#2b3040",
    shoes: str = "#1d1d21",
    hair: Optional[str] = "#2a1d16",
    location: Optional[list[float]] = None,
    facing_deg: float = 0.0,
    pose: str = "stand",
) -> dict:
    """Add a realistically proportioned adult body via the free MPFB add-on (installed into Blender on
    first use). muscle and weight run 0-1. The outfit is painted on, so keep it at medium distance.
    Same poses and clips as create_character."""
    return call("create_human", name=name, gender=gender, age=age, muscle=muscle, weight=weight, height=height,
                skin=skin, top=top, bottom=bottom, shoes=shoes, hair=hair or "none", location=location,
                facing_deg=facing_deg, pose=pose)


@mcp.tool()
def pose_character(
    character: str,
    pose: Optional[str] = None,
    bones: Optional[dict[str, list[float]]] = None,
) -> dict:
    """Pose a figure. pose is a preset (see create_character). bones sets joints by hand as
    {bone: [bend_forward, twist, raise_sideways]} degrees; figures made here have hips, spine, head, and
    upper_arm, forearm, thigh, shin ending in .L or .R (sideways raise: left positive, right negative).
    Posing removes animation."""
    return call("pose_character", character=character, pose=pose, bones=bones)


@mcp.tool()
def animate_character(
    character: str,
    clip: Literal["walk", "run", "wave", "idle", "jump", "dance"],
    seconds: float = 4.0,
    start_seconds: float = 0.0,
    distance: float = 0.0,
) -> dict:
    """Make a create_character or create_human figure move. distance carries it forward that many metres over the clip
    (about 1.3 m per second suits walk, 4 for run). Clips can follow one another using start_seconds."""
    return call("animate_character", character=character, clip=clip, seconds=seconds,
                start_seconds=start_seconds, distance=distance)


@mcp.tool()
def list_animations() -> dict:
    """List the rigs in the scene with their bone names, and any motion clips that came with imported files
    (for example a character downloaded from Mixamo or Ready Player Me and loaded with import_model)."""
    return call("list_animations")


@mcp.tool()
def play_animation(target: str, clip: str) -> dict:
    """Play one of an imported file's own motion clips (see list_animations) on a rig or object."""
    return call("play_animation", target=target, clip=clip)


# --- motion ----------------------------------------------------------------

@mcp.tool()
def animate(
    kind: Literal["turntable", "camera_orbit", "dolly", "bounce", "spin", "float", "grow", "light_fade"],
    target: Names = None,
    seconds: float = 4.0,
    amount: Optional[float] = None,
    start_seconds: float = 0.0,
) -> dict:
    """Add simple motion. turntable: the subject spins once, looping seamlessly. camera_orbit: the camera
    circles (amount = degrees). dolly: the camera glides in (amount = fraction of the distance).
    bounce / spin / float / grow: move the named target (amount = hop height, turns, or bob height).
    light_fade: the lights rise from darkness. Several can be combined."""
    return call("animate", kind=kind, target=target, seconds=seconds, amount=amount, start_seconds=start_seconds)


@mcp.tool()
def drop_objects(
    objects: Union[str, list[str]],
    seconds: float = 3.0,
    bounciness: float = 0.25,
    friction: float = 0.6,
    keep_animation: bool = True,
) -> dict:
    """Let objects fall, bounce and tumble with real physics until they settle on the floor and on each
    other. Start them in the air, not overlapping. With keep_animation=False only the final resting
    positions are kept, which is the way to get a naturally scattered pile for a still picture."""
    return call("drop_objects", objects=objects, seconds=seconds, bounciness=bounciness, friction=friction,
                keep_animation=keep_animation)


@mcp.tool()
def drape_cloth(
    over: Names = None,
    name: str = "Cloth",
    size: Optional[float] = None,
    color: str = "#b9c4d6",
) -> dict:
    """Drop a sheet of fabric onto objects and keep the folds: tablecloths, covers, blankets, a reveal
    sheet. It lands on the named objects (or everything) and the floor. size is the sheet's width in metres."""
    return call("drape_cloth", over=over, name=name, size=size, color=color)


@mcp.tool()
def clear_animation(objects: Names = None) -> dict:
    """Remove motion from the named objects, or from the whole scene if none are named."""
    return call("clear_animation", objects=objects)


# --- assets and files ------------------------------------------------------

@mcp.tool()
def search_assets(kind: Literal["hdri", "texture", "model"] = "hdri", query: str = "", limit: int = 15) -> dict:
    """Search Poly Haven's free library (no account needed): 'hdri' lighting environments, photographed
    'texture' surfaces, and ready-made 'model' props. Returns ids to use with the other asset tools."""
    return call("search_assets", kind=kind, query=query, limit=limit)


@mcp.tool()
def apply_texture(objects: Union[str, list[str]], asset_id: str, scale: float = 1.0) -> dict:
    """Cover objects with a photographed Poly Haven texture (brick, wood planks, marble, ...).
    scale above 1 makes the pattern smaller and repeat more."""
    return call("apply_texture", objects=objects, asset_id=asset_id, scale=scale)


@mcp.tool()
def import_asset(
    asset_id: str,
    name: Optional[str] = None,
    fit_height: Optional[float] = None,
    location: Optional[list[float]] = None,
) -> dict:
    """Add a ready-made Poly Haven model to the scene. fit_height rescales it to that many metres tall
    and stands it on the ground."""
    return call("import_asset", asset_id=asset_id, name=name, fit_height=fit_height, location=location)


@mcp.tool()
def import_model(path: str, name: Optional[str] = None, fit_height: Optional[float] = None) -> dict:
    """Import a 3D file from disk (.glb, .gltf, .obj, .stl, .fbx, .usd)."""
    return call("import_model", path=path, name=name, fit_height=fit_height)


@mcp.tool()
def export_model(path: str, include_studio: bool = False) -> dict:
    """Export the objects for use elsewhere. The file type follows the extension: .glb (web and games),
    .gltf, .obj, .stl (3D printing), .fbx, .usdc. Studio lights and backdrop are left out unless asked."""
    return call("export_model", path=path, include_studio=include_studio)


@mcp.tool()
def save_blend(path: Optional[str] = None) -> dict:
    """Save the whole scene as a .blend file that opens in Blender."""
    return call("save_blend", path=path)


@mcp.tool()
def open_in_blender() -> dict:
    """Save the scene and open it in the Blender app so the person can look around and edit it by hand."""
    saved = call("save_blend")["saved"]
    try:
        subprocess.Popen([find_blender(), saved], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except (BlenderError, OSError) as exc:
        raise ValueError(str(exc)) from None
    return {"opened": saved}


def _compact(schema):
    """Trim what the model has to read: drop auto-generated titles and collapse "X or nothing" unions."""
    if isinstance(schema, list):
        return [_compact(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    schema = {key: _compact(value) for key, value in schema.items() if key != "title"}
    options = schema.get("anyOf")
    if options:
        real = [option for option in options if option.get("type") != "null"]
        if len(real) < len(options):
            schema.pop("anyOf")
            schema.pop("default", None) if schema.get("default") is None else None
            schema = {**(real[0] if len(real) == 1 else {"anyOf": real}), **schema}
    return schema


for _tool in mcp._tool_manager._tools.values():
    _tool.parameters = _compact(_tool.parameters)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
