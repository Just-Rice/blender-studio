# Findings for cycle1

## Overall

- Pairs judged: 32. Blender Studio better in 21, plain in 7, ties 4.
- Average overall score: plain 4.31, studio 5.61.
- Checklist met: plain 73%, studio 81%.

## By model

| | Plain | Studio | Studio wins | Checklist plain | Checklist studio |
| --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5-20251001 | 1.3 | 4.1 | 8 of 8 | 14% | 62% |
| claude-haiku-5-5 | 4.7 | 5.8 | 5 of 8 | 91% | 81% |
| claude-opus-5-5 | 6.5 | 6.6 | 3 of 8 | 98% | 94% |
| claude-sonnet-5-5 | 4.8 | 5.9 | 5 of 8 | 89% | 86% |

## By request

| | Plain | Studio | Studio wins | Checklist plain | Checklist studio |
| --- | --- | --- | --- | --- | --- |
| busstop | 4.1 | 6.1 | 3 of 4 | 82% | 85% |
| cheese | 4.0 | 5.5 | 3 of 4 | 75% | 92% |
| hillside | 4.1 | 4.4 | 1 of 4 | 59% | 66% |
| mug | 4.8 | 5.6 | 3 of 4 | 75% | 88% |
| perfume | 5.2 | 5.9 | 2 of 4 | 75% | 88% |
| reading | 3.9 | 7.0 | 4 of 4 | 81% | 94% |
| robot-video | 3.9 | 5.1 | 2 of 4 | 56% | 75% |
| spill | 4.5 | 5.2 | 3 of 4 | 81% | 59% |

## Weakest criteria with Blender Studio (average across all pairs)

- overall: studio 5.61, plain 4.31
- materials: studio 5.75, plain 4.05
- composition: studio 6.11, plain 4.84
- request: studio 6.34, plain 5.58
- lighting: studio 6.39, plain 4.66

## Pairs plain Blender won, and checklist items the tools missed

- **claude-haiku-4-5-20251001__busstop** (studio won, studio 4.0 vs plain 1.5). Missed: One person is looking at a watch on their wrist. Judge: The second picture has a recognisable bus shelter, a clear waving figure and well-made character models, though the bench hides the sitting figure and the watch-checker, while the first is a broken arrangement of blocks with floating heads and nothing that reads as a bus stop.
- **claude-haiku-4-5-20251001__cheese** (studio won, studio 4.0 vs plain 1.5). Missed: A bite taken out, with a bite-shaped edge. Judge: The second shows a recognisable wedge with clearly round holes, though it is washed out and has no bite, while the first is a cropped, warped slab with slit-like dents that reads as neither a wedge nor Swiss cheese.
- **claude-haiku-4-5-20251001__hillside** (studio won, studio 3.0 vs plain 1.0). Missed: Rocky ground that rises like a hillside; A twisted or gnarled tree. Judge: The first picture is an almost empty grey frame with no hillside, boulders, tree or clouds, while the second at least shows a terrain patch with boulders, a crude tree trunk and puffy low clouds, even though it reads as a flat, untextured floating diorama rather than a hillside.
- **claude-haiku-4-5-20251001__mug** (studio won, studio 3.5 vs plain 1.0). Missed: There is a saucer under the mug. Judge: The first picture shows a recognisable white mug and saucer, cleanly lit on a seamless backdrop, but the saucer cuts through the middle of a solid, uncut cylinder; the second shows only the blurred edge of a white disc over grey, with no mug at all.
- **claude-haiku-4-5-20251001__reading** (studio won, studio 5.5 vs plain 1.0). Missed: Warm evening light. Judge: The second picture clearly shows a detailed armchair on a convincing plank floor with books and a lamp, though its light is neutral rather than warm evening; the first is a badly cropped set of plain blocks on a featureless floor that barely reads as an armchair.
- **claude-haiku-4-5-20251001__robot-video** (studio won, studio 2.5 vs plain 1.0). Missed: The robot's position changes across the frames, as if walking in; In the later frames the robot waves; The frames show a smooth progression, not identical stills. Judge: The first picture is only Blender's default grey cube with no robot and no motion, while the second shows a well-lit blocky toy robot that walks out of view instead of in, never waves, and leaves the last three frames empty.
- **claude-haiku-4-5-20251001__spill** (studio won, studio 4.0 vs plain 2.0). Missed: Toy blocks scattered as if spilled, not neatly placed; Some blocks tilted or resting on each other naturally; A cloth draped over one corner of the table, hanging in folds. Judge: The first picture is cleanly lit and has a recognisable draped cloth, though it covers a box instead of the table corner and the blocks sit in a tidy cluster; the second has no cloth, its blocks float in mid-air away from their shadows, and its flat colours and grey void look unfinished.
- **claude-haiku-5-5__busstop** (studio won, studio 6.5 vs plain 4.0). Missed: One person is looking at a watch on their wrist. Judge: Only the first picture has a readable watch check (the second figure's hand to the mouth looks more like thinking), but its washed-out, low-contrast lighting and flat grey materials fall well short of the second's well-lit, appealing characters and clear bus-stop staging.
- **claude-haiku-5-5__hillside** (tie won, studio 4.5 vs plain 3.5). Missed: Rocky ground that rises like a hillside; A twisted or gnarled tree. Judge: The second picture has proper shadows, rocks with real sculpted detail and clouds that sit low in the scene. The first is flatly lit, uses the same noisy grey texture almost everywhere, cuts off the top of the tree and keeps its clouds high in the sky, even though its hill reads more clearly as rocky.
- **claude-haiku-5-5__perfume** (plain won, studio 4.0 vs plain 8.0). Missed: A perfume bottle that clearly looks like glass, with transparency or refraction. Judge: The second picture's bottle is clearly glass, with real refraction and amber liquid under a bright chrome cap, while the first one's pink bottle looks like opaque plastic or a nail-polish bottle with no visible transparency.
- **claude-haiku-5-5__robot-video** (plain won, studio 5.5 vs plain 5.5). Missed: In the later frames the robot waves. Judge: The first has nicer spotlight lighting and a smooth walk, but its robot only lifts a hand near its head in a way that doesn't read as a wave; the second, despite flat grey lighting, plain materials, a cropped entry frame and a big jump in robot size between frames, clearly walks into view and waves.
- **claude-haiku-5-5__spill** (studio won, studio 5.5 vs plain 4.0). Missed: A cloth draped over one corner of the table, hanging in folds; Some blocks tilted or resting on each other naturally. Judge: Neither cloth hangs in real folds, but the first has cleaner framing, softer and more considered lighting, and wood-grain materials, while the second is crowded, has blocks cropped at the frame edge and shows the bare edges of the set.
- **claude-opus-5-5__cheese** (plain won, studio 5.5 vs plain 7.0). Missed: nothing. Judge: The second picture shows a clean wedge with neat round holes and a clear scalloped bite in one corner, while the first has a strange vertical fluted cut for its bite, odd heart-shaped holes and one hole on top that looks painted on, even though the second's wavy wood board is a bit distracting.
- **claude-opus-5-5__hillside** (plain won, studio 5.5 vs plain 7.0). Missed: Rocky ground that rises like a hillside. Judge: The first picture shows a real rising rocky slope with mist drifting across it, while the second has better textures and warm light but sits on nearly flat ground with a cloud that looks like a blob dropped on the grass.
- **claude-opus-5-5__mug** (plain won, studio 6.0 vs plain 8.0). Missed: The mug fills a good part of the frame. Judge: The first fills the frame with a well-modelled, cleanly lit glazed mug and saucer that looks ready for a catalogue, while the second leaves too much empty foreground, places the mug small in the frame and has coffee that looks metallic.
- **claude-opus-5-5__spill** (plain won, studio 5.5 vs plain 7.0). Missed: nothing. Judge: The second picture looks more like a real spill: the box is tipped over, blocks sit tilted, and some have fallen to the floor, while the first has an upright box, mostly upright blocks and an odd pinched knot in its cloth around a block.
- **claude-sonnet-5-5__busstop** (tie won, studio 6.0 vs plain 5.5). Missed: One person is looking at a watch on their wrist. Judge: The first picture covers the brief more fully, with a real shelter and a visible watch, but its blocky figures face away from us and look crude, while the second is far more appealing with its soft lighting and characterful figures, even though the watch is missing and the seated figure floats oddly above the bench.
- **claude-sonnet-5-5__hillside** (tie won, studio 4.5 vs plain 5.0). Missed: Rocky ground that rises like a hillside. Judge: The second picture shows a real rising hillside with large boulders and low clouds hugging the slope, while the first has glossy, plastic-looking clouds and tree on rolling ground that doesn't read as a hillside, even though its tree is more twisted.
- **claude-sonnet-5-5__perfume** (plain won, studio 5.0 vs plain 5.5). Missed: A perfume bottle that clearly looks like glass, with transparency or refraction. Judge: The first bottle reads more clearly as clear glass, with see-through edges and a believable reflection, but its flat gold liquid looks opaque; the second has better mood, yet its frosted body and glowing, solid-looking liquid read like a plastic lamp, and its cap highlights are blown out.
- **claude-sonnet-5-5__spill** (studio won, studio 6.0 vs plain 5.0). Missed: Some blocks tilted or resting on each other naturally; A cloth draped over one corner of the table, hanging in folds. Judge: The first is a cleaner, well-framed picture of a whole table, even though its cloth barely hangs over the edge and its wood grain is odd wavy stripes; the second shows the request more literally, with tilted and stacked blocks and a hanging cloth, but it's cropped awkwardly, has no visible table legs, and its flat materials and drab grey background look like an unfinished test render.

## How the tools were used

- Tool calls with Blender Studio: 841. Own code (run_python): 109 (13%).
- Never used this cycle (8 of 43): boolean, create_human, export_model, import_model, list_animations, open_in_blender, play_animation, save_blend.
- Most used: render_preview 127, run_python 109, apply_material 72, frame_camera 60, transform_object 51, create_object 42, add_backdrop 36, studio_lighting 36, set_look 35, render_final 30, add_polish 26, new_scene 25.

## Failed calls and unfinished runs

- Unfinished: claude-haiku-4-5-20251001 hillside plain: error_max_turns
- Unfinished: claude-haiku-4-5-20251001 reading plain: error_max_turns
- Unfinished: claude-haiku-4-5-20251001 robot-video plain: error_max_turns
- plain execute_python x3: Error executing tool execute_python: KeyError: 'bpy_prop_collection[key]: key "Emission" not found'
- plain execute_python x3: Error executing tool execute_python: RuntimeError: Error: Node type ShaderNodeValRamp undefined
- studio apply_material x2: Error executing tool apply_material: ValueError: Unknown preset 'metal'. Choose from: plastic_glossy, plastic_matte, rubber, clay, ceramic, porcelain, steel, ch
- plain execute_python x2: Error executing tool execute_python: TypeError: ObjectModifiers.new(): error with keyword argument "type" -  enum "SUBDIVISION" not found in ('GREASE_PENCIL_VER
- studio apply_material x2: Error executing tool apply_material: 2 validation errors for apply_materialArguments
color.str
  Input should be a valid string [type=string_type, input_value=[
- studio import_asset x2: Error executing tool import_asset: ValueError: 'decorative_book_set_01' is not a Poly Haven model. Use search_assets(kind='model').
- studio apply_material x2: Error executing tool apply_material: ValueError: Unknown preset 'cardboard'. Choose from: plastic_glossy, plastic_matte, rubber, clay, ceramic, porcelain, steel
- plain render_image x1: Error executing tool render_image: ValueError: The scene has no active camera.
- plain execute_python x1: Error executing tool execute_python: NameError: name 'Vector' is not defined
- plain execute_python x1: Error executing tool execute_python: KeyError: 'bpy_prop_collection[key]: key "Specular IOR" not found'
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'SimpleDeformModifier' object has no attribute 'deform_type'
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'SimpleDeformModifier' object has no attribute 'mode'
- plain execute_python x1: Error executing tool execute_python: KeyError: 'bpy_prop_collection[key]: key "Bsdf" not found'
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'AreaLight' object has no attribute 'angle'
- plain execute_python x1: Error executing tool execute_python: KeyError: 'bpy_prop_collection[key]: key "Light" not found'
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'RenderSettings' object has no attribute 'use_denoising'
- studio run_python x1: Error executing tool run_python: TypeError: Converting py args to operator properties:
- studio search_assets x1: Error executing tool search_assets: SSLError: HTTPSConnectionPool(host='api.polyhaven.com', port=443): Max retries exceeded with url: /assets?t=hdris (Caused by
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'NoneType' object has no attribute 'location' and no __dict__ for setting new attributes
- plain execute_python x1: Error executing tool execute_python: ModuleNotFoundError: No module named 'PIL'
- plain execute_python x1: Error executing tool execute_python: AttributeError: Calling operator "bpy.ops.object.material_slots_add" error, could not be found
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'SceneEEVEE' object has no attribute 'use_bloom'
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'SceneEEVEE' object has no attribute 'use_gtao'
- plain execute_python x1: Error executing tool execute_python: AttributeError: 'PointLight' object has no attribute 'size'
- studio apply_texture x1: Error executing tool apply_texture: ValueError: Could not fetch 'grass_meadow' from Poly Haven (404 Client Error: Not Found for url: https://api.polyhaven.com/f

## Cost and effort (totals)

| Model | Way | Cost | Tokens read | Tokens written | Model time | Total time |
| --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5-20251001 | plain | $1.61 | 5140k | 103k | 951 s | 16154 s |
| claude-haiku-4-5-20251001 | studio | $1.09 | 4005k | 49k | 552 s | 5826 s |
| claude-haiku-5-5 | plain | $0.08 | 933k | 84k | 412 s | 1341 s |
| claude-haiku-5-5 | studio | $0.13 | 3134k | 95k | 514 s | 1866 s |
| claude-opus-5-5 | plain | $3.20 | 1300k | 81k | 759 s | 9988 s |
| claude-opus-5-5 | studio | $3.43 | 2482k | 70k | 666 s | 3599 s |
| claude-sonnet-5-5 | plain | $0.47 | 203k | 21k | 159 s | 1444 s |
| claude-sonnet-5-5 | studio | $0.67 | 931k | 22k | 177 s | 1329 s |
