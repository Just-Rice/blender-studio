# Blender Studio design guide

Good 3D pictures come from craft choices, not from complicated models. Follow these.

## The loop
- Build, then `scene_check`, then `render_preview`, then look hard at the picture and name what is wrong.
- Change one or two things, render again. Expect three to six rounds. Stop when nothing bothers you.
- Use `contact_sheet` whenever you build something from several parts: parts that look joined from the
  front are often floating apart from the side.
- `render_final` is last, and only once.

## Shape
- Nothing in the real world has a perfectly sharp edge. Run `add_polish` on almost everything.
  Use bevel 0.02 for realistic products, 0.06-0.12 for friendly, toy-like or cartoon objects.
- Get proportions right before anything else. Pick a real size in metres and keep to it
  (a mug is 0.1 m tall, a chair seat is 0.45 m high, a person is 1.7 m).
- Build objects sitting on Z = 0. Parts must overlap slightly where they join, never just touch.
- Fewer, better shapes beat many rough ones. Vary size: one large, a few medium, some small.

## Organic shapes
- Nature is never a perfect primitive. Use `create_rock` and `create_terrain` for ground and stone,
  `create_blob` for soft rounded masses (clouds, bodies, bushes), `create_limbs` for anything with
  branches or a spine (trees, creatures, tentacles, handles).
- `sculpt` with a little roughness (0.03-0.08) makes any hard shape look hand-made; more makes it lumpy.
- `boolean` cuts windows, holes and bites. Keep the cutter clearly overlapping the target.
- Vary `seed` so repeated rocks and hills are not clones. Scatter them in odd numbers and mixed sizes.

## People
- `create_character` for stylised scenes: 'toy' for friendly, 'lowpoly' to match faceted scenery,
  'blocky' for voxel worlds. Match the figure's style to the rest of the scene.
- `create_human` for a realistic body. Keep it at medium distance; the painted outfit and simple
  face do not survive a close-up.
- A pose tells the story. Never leave a figure in the default stand if it is meant to be doing something.
- Turn figures with `facing_deg` so they look at each other or at the subject, not all at the camera.
- A person is 1.7 m. Use that to sanity-check the size of everything else.

## Motion
- Decide the one thing that moves. A turntable or slow camera orbit is enough for a product;
  add character or object motion only when it says something.
- Three to five seconds is plenty. Loops (`turntable`, a full `camera_orbit`) should be seamless.
- `drop_objects` with `keep_animation=False` gives a natural scatter for a still picture.
- Check motion with `render_preview(at_seconds=...)` at a few moments before paying for `render_animation`.
- `render_animation` returns a strip of frames: check that nothing leaves the frame, sinks into the
  floor or passes through something else.

## Materials
- Use at most three materials in a scene, and make them contrast: one matte, one glossy or metallic.
- Roughness variety is what makes a render look real. All-glossy and all-matte both look fake.
- Keep colours slightly off pure. Never `#ff0000` or `#ffffff`; try `#d6332b` and `#f2efe9`.
- Pick a palette before you start: one dominant colour (about 60%), one secondary (30%), one accent (10%).
  The backdrop is usually the dominant colour, so choose it to flatter the subject: a muted tint of the
  subject's complementary colour, or a soft neutral.
- Glass and chrome only look good with something to reflect: use `studio_lighting(style="hdri")`.

## Lighting
- `softbox` for clean product shots, `three_point` for characters and general subjects,
  `golden_hour` for outdoor warmth, `dramatic` or `neon` for mood, `hdri` for realism and reflections.
- Shadows give shape. If the picture looks flat, the light is too even: try `dramatic`, or lower strength
  and raise contrast with `set_look`.
- Always have a ground (`add_backdrop`). A subject with no shadow looks pasted on.
- Dark backdrop with a rim light separates a dark subject; light backdrop suits a colourful one.

## Camera
- `three_quarter` is the reliable hero angle. `front` and `isometric` suit graphic or game art.
- Longer lenses (70-100 mm) flatter products and faces. Wide lenses (24-28 mm) add drama and scale.
- Leave breathing room: the default fill of 0.78 is right for most shots; do not crop the subject by accident.
- A little `depth_of_field` (f/2.8 to f/5.6) on close subjects reads as photographic. Skip it for
  isometric and diagram styles.
- Match aspect to purpose: 1:1 or 4:5 for icons and social posts, 16:9 for banners, 9:16 for phones.

## Look
- `product_clean` when in doubt. `vivid` for playful, `cinematic` or `moody` for atmosphere,
  `soft_pastel` for gentle and friendly, `flat_graphic` when colours must match exactly.
- Heed exposure warnings from `render_preview`: blown-out whites and crushed blacks lose detail.

## Judging your own render
Ask each time:
- Can I tell what it is within one second?
- Is there one clear focal point, and is it the brightest or most contrasting thing?
- Does every object sit on something and cast a shadow?
- Are there any razor edges, plain grey objects, or parts poking through each other?
- Would this look at home in a design portfolio? If not, what is the single biggest thing letting it down?

## When things go wrong
- Every change is checkpointed. `undo` steps back; it is cheaper than repairing a mess.
- A tool that fails rolls the scene back by itself, so read the error, fix the call and try again.
- Brush-level sculpting, photoreal faces, real clothing and hand-keyed acting are beyond these tools.
  Use `import_asset` or `import_model` for complex ready-made objects and characters, and concentrate
  on staging them well. Imported characters keep their own motion: see `list_animations`.
