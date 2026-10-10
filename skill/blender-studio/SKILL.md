---
name: blender-studio
description: Make 3D art, renders, product shots, low-poly scenes or 3D models with Blender through the blender-studio MCP tools. Use whenever the user asks for a 3D picture, render, model or .glb/.blend file.
---

# Blender Studio

The `blender-studio` MCP tools drive a real copy of Blender, which starts by itself on the first call.

1. Call `design_guide` once and follow it. It holds the rules for shape, materials, lighting, camera and look.
2. Decide a palette, a real-world size and a mood before building anything.
3. Build the subject: `create_object`, `import_asset`, and `run_python` for custom shapes. Use
   `create_rock`, `create_terrain`, `create_blob`, `create_limbs`, `sculpt` and `boolean` for organic
   forms, and `create_character` or `create_human` for people.
4. Finish it: `apply_material`, `add_polish`, `add_backdrop`.
5. Stage it: `studio_lighting`, `frame_camera`, `set_look`.
6. `scene_check`, then `render_preview`, and look at the picture critically. Use `contact_sheet` for anything
   made of several parts. Fix and repeat; expect three to six rounds.
7. For motion, add `animate`, `animate_character` or `drop_objects`, check a few moments with
   `render_preview(at_seconds=...)`, then `render_animation` for the video.
8. `render_final` once the preview is right. Tell the user where the file was saved, and offer
   `open_in_blender` or `export_model` if they want to keep working on it.

Never report a scene as finished without having looked at a render of it.
