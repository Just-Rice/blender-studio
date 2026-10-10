"""Overall image look: contrast, exposure and glow."""
import bpy

from .. import util
from ..commands import command

LOOKS = {
    "product_clean": dict(contrast="Medium High Contrast", exposure=0.0, bloom=0.0,
                          about="Neutral and crisp. Catalogue and product shots."),
    "cinematic": dict(contrast="High Contrast", exposure=-0.15, bloom=0.35,
                      about="Deeper shadows with a soft glow on highlights."),
    "soft_pastel": dict(contrast="Medium Low Contrast", exposure=0.35, bloom=0.15,
                        about="Bright, gentle and airy."),
    "moody": dict(contrast="Very High Contrast", exposure=-0.5, bloom=0.25,
                  about="Dark and dramatic."),
    "vivid": dict(contrast="Punchy", exposure=0.1, bloom=0.2,
                  about="Saturated and energetic. Toys, games, neon."),
    "flat_graphic": dict(transform="Standard", contrast=None, exposure=0.0, bloom=0.0,
                         about="Colours appear exactly as chosen. Icons, isometric and low-poly art."),
    "black_and_white": dict(contrast="Greyscale", exposure=0.0, bloom=0.0, about="Monochrome."),
}


def _set_contrast(view, name):
    if name is None:
        view.look = "None"
        return "None"
    for candidate in (f"{view.view_transform} - {name}", name, f"AgX - {name}", "None"):
        try:
            view.look = candidate
            return candidate
        except TypeError:
            continue


def _bloom(scene, amount):
    """Highlight glow through the compositor. Returns False where this Blender cannot do it."""
    try:
        if hasattr(scene, "compositing_node_group"):
            if amount <= 0:
                scene.compositing_node_group = None
                return True
            tree = bpy.data.node_groups.new("Studio Look", "CompositorNodeTree")
            tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            out = tree.nodes.new("NodeGroupOutput")
            scene.compositing_node_group = tree
        else:
            scene.use_nodes = amount > 0
            if amount <= 0:
                return True
            tree = scene.node_tree
            tree.nodes.clear()
            out = tree.nodes.new("CompositorNodeComposite")
        layers = tree.nodes.new("CompositorNodeRLayers")
        glare = tree.nodes.new("CompositorNodeGlare")
        if "Type" in glare.inputs:
            glare.inputs["Type"].default_value = "Bloom"
        else:
            glare.glare_type = "BLOOM"
        for key, value in (("Strength", amount), ("Threshold", 1.0), ("Size", 0.6)):
            if key in glare.inputs:
                glare.inputs[key].default_value = value
        tree.links.new(layers.outputs[0], glare.inputs[0])
        tree.links.new(glare.outputs[0], out.inputs[0])
        return True
    except Exception:
        return False


@command()
def set_look(preset="product_clean", exposure=None, bloom=None):
    preset = preset.lower()
    if preset not in LOOKS:
        raise ValueError(f"Unknown look '{preset}'. Choose from: {', '.join(LOOKS)}")
    spec = LOOKS[preset]
    scene = bpy.context.scene
    view = scene.view_settings
    try:
        view.view_transform = spec.get("transform", "AgX")
    except TypeError:
        view.view_transform = "Filmic" if "transform" not in spec else "Standard"
    contrast = _set_contrast(view, spec["contrast"])
    view.exposure = spec["exposure"] if exposure is None else exposure
    amount = spec["bloom"] if bloom is None else bloom
    result = {"look": preset, "tone": f"{view.view_transform} / {contrast}", "exposure": view.exposure}
    result["bloom"] = amount if _bloom(scene, amount) else "not available in this Blender version"
    return result
