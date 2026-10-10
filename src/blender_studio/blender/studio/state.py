"""Session folders and file-snapshot undo (works the same with or without a window)."""
import os
import tempfile
import time

import bpy

MAX_CHECKPOINTS = 15

session_dir = ""
_checkpoints = []
_counter = 0


def init(path):
    global session_dir
    session_dir = path or tempfile.mkdtemp(prefix="blender-studio-")
    for sub in ("renders", "checkpoints", "cache"):
        os.makedirs(os.path.join(session_dir, sub), exist_ok=True)


def subdir(name):
    return os.path.join(session_dir, name)


def cache_dir():
    path = os.path.expanduser("~/.cache/blender-studio")
    os.makedirs(path, exist_ok=True)
    return path


def render_path(label, ext="png"):
    stamp = time.strftime("%H%M%S")
    return os.path.join(subdir("renders"), f"{stamp}-{label}.{ext}")


def checkpoint(label):
    """Snapshot the scene before a change so undo() can bring it back."""
    global _counter
    _counter += 1
    path = os.path.join(subdir("checkpoints"), f"{_counter:05d}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, check_existing=False)
    _checkpoints.append((path, label))
    while len(_checkpoints) > MAX_CHECKPOINTS:
        old, _ = _checkpoints.pop(0)
        for stale in (old, old + "1"):
            if os.path.exists(stale):
                os.remove(stale)


def undo(steps=1):
    if not _checkpoints:
        raise ValueError("Nothing to undo: no checkpoints yet.")
    steps = max(1, min(int(steps), len(_checkpoints)))
    undone = []
    for _ in range(steps):
        path, label = _checkpoints.pop()
        undone.append(label)
    bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
    return {"undone": undone, "remaining_checkpoints": len(_checkpoints)}
