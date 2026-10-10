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

Never finish without looking at a render. Call design_guide once before your first scene for the craft rules.
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
    objects: Union[str, list[str]],
    preset: str,
    color: Color = None,
    roughness: Optional[float] = None,
    metallic: Optional[float] = None,
    emission_strength: Optional[float] = None,
) -> dict:
    """Give objects a realistic surface. Presets include plastic_glossy, plastic_matte, rubber, clay, ceramic,
    porcelain, steel, chrome, gold, copper, aluminium, car_paint, glass, frosted_glass, water, wood, fabric,
    velvet, concrete, stone, skin, wax, glow, neon_tube. color is '#rrggbb'; leave it out for the natural colour."""
    return call("apply_material", objects=objects, preset=preset, color=color, roughness=roughness,
                metallic=metallic, emission_strength=emission_strength)


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
) -> dict:
    """Put the subject on a surface so it has a shadow and a horizon. 'cyclorama' is a seamless photo-studio
    sweep (floor curving up into a wall); 'floor' is a wide flat ground. It is placed under the lowest object."""
    return call("add_backdrop", style=style, color=color, roughness=roughness)


@mcp.tool()
def studio_lighting(
    style: Literal["three_point", "softbox", "golden_hour", "overcast", "dramatic", "neon", "hdri"] = "three_point",
    strength: float = 1.0,
    subjects: Names = None,
    hdri: Optional[str] = None,
    hdri_rotation_deg: float = 0.0,
) -> dict:
    """Replace all lighting with a complete rig sized and aimed at the subject. strength scales brightness
    (0.5 dimmer, 2 brighter). For style='hdri', pass a Poly Haven HDRI id from search_assets (default is a studio)."""
    return call("studio_lighting", style=style, strength=strength, subjects=subjects, hdri=hdri,
                hdri_rotation_deg=hdri_rotation_deg)


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
    """Place the camera so the subject is centred and fills the frame. Override the angle with azimuth_deg
    (0 front, 90 right side, 180 back) and elevation_deg (0 eye level, 90 overhead). fill is how much of the
    frame the subject takes (default 0.78). depth_of_field is an f-stop: 1.8 blurs the background strongly,
    8 slightly; leave empty for everything sharp. subjects limits framing to named objects."""
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
def render_preview(quality: Literal["draft", "preview"] = "preview") -> list:
    """Render the camera view quickly and return the picture so you can judge it. 'draft' is half size and
    fastest. Look closely at composition, lighting and materials, then fix and render again."""
    return _render(quality)


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
    cell_w, cell_h, columns = 480, 360, 3
    rows = -(-len(views) // columns)
    sheet = PILImage.new("RGB", (cell_w * columns, cell_h * rows), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for index, view in enumerate(views):
        x, y = (index % columns) * cell_w, (index // columns) * cell_h
        sheet.paste(PILImage.open(view["path"]).convert("RGB").resize((cell_w, cell_h)), (x, y))
        draw.rectangle((x, y, x + 12 + 8 * len(view["label"]), y + 22), fill=(0, 0, 0))
        draw.text((x + 6, y + 5), view["label"], fill=(255, 255, 255))
    return [_jpeg(sheet, 1440), "Views: " + ", ".join(view["label"] for view in views)]


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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
