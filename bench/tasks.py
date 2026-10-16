"""The benchmark requests. Each one needs a particular kind of feature to be done well, without naming any tool,
so plain Blender can attempt every one of them too.

checklist: concrete things the judge ticks yes or no before scoring, so "did it do what was asked" is measured
           separately from "does it look good".
holdout:   run only every third cycle and never used to choose fixes, so improvements on the regular requests
           can be checked for overfitting.
video:     the answer is a short animation, judged from a strip of evenly spaced frames.
"""

TASKS = {
    "mug": dict(
        brief="A ceramic coffee mug on a saucer, photographed as a product shot for a homeware catalogue.",
        needs="materials, lighting, framing",
        checklist=["A mug is clearly visible", "There is a saucer under the mug",
                   "It reads as a ceramic product on a clean, deliberate background",
                   "The mug fills a good part of the frame"]),
    "hillside": dict(
        brief="A rocky hillside with a few large boulders, a twisted old tree and low clouds drifting past.",
        needs="terrain, rocks, organic shapes",
        checklist=["Rocky ground that rises like a hillside", "Several large boulders",
                   "A twisted or gnarled tree", "Low clouds or mist"]),
    "busstop": dict(
        brief="Three people at a bus stop: one waving to someone, one sitting on the bench, one checking their watch.",
        needs="people, poses",
        checklist=["Exactly three people", "One person is waving", "One person is sitting",
                   "One person is looking at a watch on their wrist", "A bus stop sign or shelter"]),
    "spill": dict(
        brief="A box of toy blocks has just spilled across a table, and a cloth is draped over one corner of the table.",
        needs="physics, cloth",
        checklist=["A table", "Toy blocks scattered as if spilled, not neatly placed",
                   "Some blocks tilted or resting on each other naturally",
                   "A cloth draped over one corner of the table, hanging in folds"]),
    "reading": dict(
        brief="A cosy reading corner: an armchair on a wooden floor, lit by warm evening light.",
        needs="ready-made models, textures, environment lighting",
        checklist=["An armchair", "A wooden floor with visible boards or grain", "Warm evening light",
                   "Something that makes it a reading corner, such as a lamp, books, a rug or a window"]),
    "perfume": dict(
        brief="A glass perfume bottle with a chrome cap, photographed as a luxury product shot.",
        needs="glass, metal, reflections",
        checklist=["A perfume bottle that clearly looks like glass, with transparency or refraction",
                   "A chrome or polished metal cap", "A deliberate luxury product-shot presentation"]),
    "cheese": dict(
        brief="A wedge of Swiss cheese with round holes, with a bite taken out of one corner.",
        needs="cutting and sculpting shapes",
        checklist=["A wedge of cheese", "Round holes in the cheese", "A bite taken out, with a bite-shaped edge"]),
    "robot-video": dict(
        brief="A 3-second video: a toy robot walks into view and waves. Finish by showing a strip of frames from it.",
        needs="animation, video", video=True,
        checklist=["A toy robot", "The robot's position changes across the frames, as if walking in",
                   "In the later frames the robot waves", "The frames show a smooth progression, not identical stills"]),
    "market": dict(
        brief="A fruit market stall at dusk: the vendor is waving, apples have tumbled onto a cloth on the counter, "
              "and a lantern lights the scene.",
        needs="many features at once", holdout=True,
        checklist=["A market stall", "A vendor who is waving", "Apples tumbled onto a cloth",
                   "A lantern giving light", "Dusk"]),
    "campsite": dict(
        brief="A low-poly campsite at dusk: a tent, a campfire and three pine trees.",
        needs="staging", holdout=True,
        checklist=["A tent", "A campfire", "Three pine trees", "A low-poly style", "Dusk"]),
    # Earlier rounds used this name for the campsite; kept so their runs can still be read.
    "camp": dict(brief="A low-poly campsite at dusk: a tent, a campfire and three pine trees.", needs="staging",
                 retired=True, checklist=["A tent", "A campfire", "Three pine trees", "A low-poly style", "Dusk"]),
    "robot": dict(brief="A friendly toy robot waving hello.", needs="modelling", retired=True,
                  checklist=["A toy robot", "It looks friendly", "It is waving"]),
}

REGULAR = [name for name, task in TASKS.items() if not task.get("holdout") and not task.get("retired")]
HOLDOUT = [name for name, task in TASKS.items() if task.get("holdout")]
