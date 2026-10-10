"""Small finishing touches that stop objects looking computer-generated: soft edges and smooth surfaces."""
import math

import bpy

from .. import util
from ..commands import command


@command()
def add_polish(objects=None, bevel=0.02, bevel_segments=3, subdivision=0, smooth=True):
    """bevel is a fraction of the object's smallest side (0.02 = 2%); 0 turns it off."""
    polished = []
    for obj in util.require_subjects(objects):
        if obj.type != "MESH":
            continue
        for modifier in [m for m in obj.modifiers if m.name.startswith("Studio ")]:
            obj.modifiers.remove(modifier)
        sides = [d for d in obj.dimensions if d > 1e-6]
        if bevel and sides:
            # Modifier widths are in local units, so undo the object's own scale.
            scale = max(sum(abs(s) for s in obj.scale) / 3, 1e-6)
            mod = obj.modifiers.new("Studio Bevel", "BEVEL")
            mod.width = bevel * min(sides) / scale
            mod.segments = bevel_segments
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(40)
            util.set_if(mod, "harden_normals", True)
        if subdivision:
            mod = obj.modifiers.new("Studio Subdivision", "SUBSURF")
            mod.levels = mod.render_levels = int(subdivision)
        if smooth:
            for poly in obj.data.polygons:
                poly.use_smooth = True
            mod = obj.modifiers.new("Studio Normals", "WEIGHTED_NORMAL")
            mod.keep_sharp = True
            mod.weight = 80
        obj.data.update()
        polished.append(obj.name)
    if not polished:
        raise ValueError("No mesh objects to polish.")
    return {"polished": polished, "bevel": bevel, "subdivision": subdivision, "smooth": smooth}
