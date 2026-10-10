"""Entry point run inside Blender: `blender [-b] --python bridge_main.py -- --port N`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from studio import bridge  # noqa: E402

bridge.main()
