# Blender Studio MCP

Lets Claude and other AI models make good-looking 3D art in [Blender](https://www.blender.org).

Blender can already be scripted, but an AI writing raw scripts tends to produce flat, grey
"programmer art". Blender Studio gives the AI what a photographer has: ready-made lighting rigs,
real materials, a camera that frames the subject by itself, and above all the ability to
**render, look at the picture, and fix it**.

| | | |
| --- | --- | --- |
| ![Ceramic mug product shot](docs/mug.jpg) | ![Low-poly island](docs/island.jpg) | ![Neon sign](docs/neon.jpg) |

*Each picture was built and photographed using only the tools below; see `examples/showcase.py`.*

- Works on macOS, Windows and Linux.
- Works with any AI app that supports MCP (Claude Code, Claude Desktop, Cursor, and others).
- Free. No account and no API key. Blender runs on your own computer.
- Blender starts by itself in the background; there is no add-on to install.

## Install

1. Install [Blender](https://www.blender.org/download/) 4.2 or newer.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
3. Add the server to your AI app.

**Claude Code**

```
claude mcp add blender-studio -- uvx --from git+https://github.com/Just-Rice/blender-studio blender-studio-mcp
```

**Claude Desktop, Cursor and other apps** (add to the app's MCP settings file)

```json
{
  "mcpServers": {
    "blender-studio": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Just-Rice/blender-studio", "blender-studio-mcp"]
    }
  }
}
```

Then ask for something: *"Make a product shot of a ceramic mug on a warm backdrop."*

## What the AI can do

| Tool | What it does |
| --- | --- |
| `create_object`, `transform_object`, `delete_objects` | Build with basic shapes |
| `run_python` | Anything else, using Blender's own scripting |
| `apply_material` | 24 realistic surfaces: ceramic, gold, glass, wood, fabric, neon and more |
| `add_polish` | Soft edges and smooth shading, so objects catch the light |
| `add_backdrop` | Seamless photo-studio sweep or a floor |
| `studio_lighting` | Seven complete rigs, sized and aimed at the subject automatically |
| `frame_camera` | Nine shot types with automatic framing, lens choice and background blur |
| `set_look` | Seven overall moods: clean, cinematic, pastel, moody, vivid, flat, monochrome |
| `scene_check` | Finds floating objects, missing lights, subjects out of frame and more |
| `render_preview`, `contact_sheet` | Shows the AI its own work, with exposure warnings |
| `render_final` | Full-quality image |
| `search_assets`, `apply_texture`, `import_asset` | Free lighting, textures and models from [Poly Haven](https://polyhaven.com) |
| `import_model`, `export_model`, `save_blend`, `open_in_blender` | Files in and out (.glb, .obj, .stl, .fbx, .usd, .blend) |
| `undo` | Steps back through the last 15 changes |
| `design_guide`, `list_presets` | The craft rules and the full preset list |

Pictures and scene files are saved in a `BlenderStudio` folder in your home folder.

## Options

Set these as environment variables in the MCP settings if you need them.

| Variable | Purpose |
| --- | --- |
| `BLENDER_PATH` | Where Blender is, if it is not found automatically |
| `BLENDER_STUDIO_WINDOW=1` | Show the Blender window and watch the scene being built live |
| `BLENDER_STUDIO_HOME` | Where to save renders and scene files |

## How it works

The MCP server starts Blender with a small bridge script loaded, then sends it one command at a
time over a local connection that only your own computer can reach. Nothing is sent anywhere
except asset downloads from Poly Haven when the AI asks for them.

## Safety

`run_python` lets the AI run code inside Blender, with the same access to your files as any
program you run. Use it with AI apps you trust, and keep their approval prompts switched on.

## Development

```
git clone https://github.com/Just-Rice/blender-studio
cd blender-studio
uv run python tests/smoke.py              # builds and renders a test scene
uv run python tests/mcp_client.py         # talks to the server the way an AI app does
uv run python examples/showcase.py out    # renders the three pictures above
uv run blender-studio-mcp                 # runs the server
```

Claude Code users can also copy `skill/blender-studio` into `~/.claude/skills/` for a short workflow reminder.

Tested with Blender 5.2. MIT licence.
