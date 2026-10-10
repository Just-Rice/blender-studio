"""Free assets from Poly Haven (CC0, no account or key): lighting photos, textures and models."""
import json
import os
import urllib.request

import bpy

from .. import state, util
from ..commands import command

API = "https://api.polyhaven.com"
HEADERS = {"User-Agent": "blender-studio/0.1"}
KINDS = {"hdri": "hdris", "texture": "textures", "model": "models"}


def _get(url):
    try:
        import requests
        response = requests.get(url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        return response.content
    except ImportError:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
            return response.read()


def _download(url, folder, filename=None):
    path = os.path.join(state.cache_dir(), folder, filename or url.rsplit("/", 1)[-1])
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = _get(url)
        with open(path + ".part", "wb") as handle:
            handle.write(data)
        os.replace(path + ".part", path)
    return path


def _files(asset_id):
    try:
        return json.loads(_get(f"{API}/files/{asset_id}"))
    except Exception as exc:
        raise ValueError(f"Could not fetch '{asset_id}' from Poly Haven ({exc}). "
                         "Check the id with search_assets, and the internet connection.")


def _pick(options, resolution):
    for res in (resolution, "2k", "1k", "4k"):
        if res in options:
            return options[res]
    return next(iter(options.values()))


def fetch_hdri(asset_id, resolution="2k"):
    files = _files(asset_id)
    if "hdri" not in files:
        raise ValueError(f"'{asset_id}' is not a Poly Haven HDRI. Use search_assets(kind='hdri').")
    choice = _pick(files["hdri"], resolution)
    return _download((choice.get("hdr") or choice["exr"])["url"], "hdri")


@command(mutates=False)
def search_assets(kind="hdri", query="", limit=15):
    kind = kind.lower()
    if kind not in KINDS:
        raise ValueError(f"Unknown kind '{kind}'. Choose from: {', '.join(KINDS)}")
    catalogue = json.loads(_get(f"{API}/assets?t={KINDS[kind]}"))
    words = query.lower().split()
    hits = []
    for asset_id, info in catalogue.items():
        text = " ".join([asset_id, info.get("name", ""), *info.get("categories", []), *info.get("tags", [])]).lower()
        if all(word in text for word in words):
            hits.append((info.get("download_count", 0), asset_id, info))
    hits.sort(key=lambda hit: hit[0], reverse=True)
    return {"kind": kind, "matches": len(hits), "results": [
        {"id": asset_id, "name": info.get("name"), "categories": info.get("categories", [])[:5]}
        for _, asset_id, info in hits[:limit]]}


@command()
def apply_texture(objects, asset_id, scale=1.0, resolution="1k"):
    """Cover objects in a photographed Poly Haven surface (wood, brick, fabric, ...). No UV mapping needed."""
    files = _files(asset_id)
    maps = {}
    for key, names in (("color", ("Diffuse", "diff", "Color")), ("rough", ("Rough", "rough")),
                       ("normal", ("nor_gl",)), ("height", ("Displacement", "disp"))):
        for name in names:
            if name in files:
                choice = _pick(files[name], resolution)
                maps[key] = _download((choice.get("jpg") or choice.get("png") or next(iter(choice.values())))["url"],
                                      f"textures/{asset_id}")
                break
    if "color" not in maps:
        raise ValueError(f"'{asset_id}' is not a Poly Haven texture. Use search_assets(kind='texture').")

    material = bpy.data.materials.new(asset_id)
    util.enable_nodes(material)
    tree = material.node_tree
    shader = tree.nodes.get("Principled BSDF")
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    tree.links.new(coords.outputs["Object"], mapping.inputs[0])

    def image(path, is_color):
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(path, check_existing=True)
        node.projection, node.projection_blend = "BOX", 0.25
        if not is_color:
            node.image.colorspace_settings.name = "Non-Color"
        tree.links.new(mapping.outputs[0], node.inputs[0])
        return node.outputs[0]

    tree.links.new(image(maps["color"], True), shader.inputs["Base Color"])
    if "rough" in maps:
        tree.links.new(image(maps["rough"], False), shader.inputs["Roughness"])
    if "normal" in maps:
        normal = tree.nodes.new("ShaderNodeNormalMap")
        tree.links.new(image(maps["normal"], False), normal.inputs["Color"])
        tree.links.new(normal.outputs[0], shader.inputs["Normal"])

    applied = []
    for obj in util.subjects(objects):
        if hasattr(obj.data, "materials"):
            obj.data.materials.clear()
            obj.data.materials.append(material)
            applied.append(obj.name)
    return {"texture": asset_id, "applied_to": applied, "maps": sorted(maps)}


@command()
def import_asset(asset_id, name=None, fit_height=None, location=None, resolution="1k"):
    """Bring in a ready-made Poly Haven model (furniture, plants, props, ...)."""
    files = _files(asset_id)
    if "gltf" not in files:
        raise ValueError(f"'{asset_id}' is not a Poly Haven model. Use search_assets(kind='model').")
    entry = _pick(files["gltf"], resolution)["gltf"]
    folder = f"models/{asset_id}"
    main = _download(entry["url"], folder)
    for relative, extra in entry.get("include", {}).items():
        _download(extra["url"], os.path.join(folder, os.path.dirname(relative)), os.path.basename(relative))
    from .scene import import_model
    result = import_model(main, name=name or asset_id, fit_height=fit_height)
    if location:
        for root in result["roots"]:
            obj = bpy.data.objects[root]
            obj.location = [a + b for a, b in zip(obj.location, location)]
    return result
