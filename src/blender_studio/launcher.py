"""Finds Blender on any OS, starts it with the bridge loaded, and talks to it over a local socket."""
import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

BRIDGE = Path(__file__).parent / "blender" / "bridge_main.py"
DOWNLOAD_HINT = (
    "Blender was not found. Install it free from https://www.blender.org/download/ "
    "(version 4.2 or newer), or set the BLENDER_PATH environment variable to the Blender program."
)


class BlenderError(Exception):
    pass


def find_blender():
    override = os.environ.get("BLENDER_PATH")
    if override:
        if os.path.exists(override):
            return override
        raise BlenderError(f"BLENDER_PATH points to '{override}', which does not exist.")
    candidates = []
    if sys.platform == "darwin":
        candidates += ["/Applications/Blender.app/Contents/MacOS/Blender",
                       os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender")]
    elif sys.platform == "win32":
        for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            candidates += sorted(glob.glob(os.path.join(root, "Blender Foundation", "Blender*", "blender.exe")),
                                 reverse=True)
            candidates.append(os.path.join(root, "Steam", "steamapps", "common", "Blender", "blender.exe"))
    else:
        candidates += ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender",
                       "/var/lib/flatpak/exports/bin/org.blender.Blender",
                       os.path.expanduser("~/.local/share/flatpak/exports/bin/org.blender.Blender"),
                       os.path.expanduser("~/.steam/steam/steamapps/common/Blender/blender")]
        candidates += sorted(glob.glob(os.path.expanduser("~/blender-*/blender")), reverse=True)
    for path in candidates:
        if os.path.exists(path):
            return path
    on_path = shutil.which("blender")
    if on_path:
        return on_path
    raise BlenderError(DOWNLOAD_HINT)


def _free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def new_session_dir():
    home = Path(os.environ.get("BLENDER_STUDIO_HOME") or Path.home() / "BlenderStudio")
    path = home / time.strftime("%Y-%m-%d_%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    return path


class Blender:
    """One Blender process and the connection to it. Started on first use."""

    def __init__(self):
        self.process = None
        self.stream = None
        self.session_dir = None
        self.lock = threading.Lock()

    def _start(self):
        self.session_dir = new_session_dir()
        attach = os.environ.get("BLENDER_STUDIO_PORT")
        if attach:
            port = int(attach)
        else:
            port = _free_port()
            show_window = os.environ.get("BLENDER_STUDIO_WINDOW", "").lower() in ("1", "true", "yes")
            command = [find_blender()]
            if not show_window:
                command += ["--background", "--factory-startup"]
            command += ["--python", str(BRIDGE), "--", "--port", str(port),
                        "--session-dir", str(self.session_dir), "--watch-stdin"]
            if os.environ.get("BLENDER_STUDIO_KEEP_SCENE"):
                command.append("--keep-startup-scene")
            log = open(self.session_dir / "blender.log", "wb")
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.time() + 90
        while True:
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=2)
                break
            except OSError:
                if self.process and self.process.poll() is not None:
                    raise BlenderError(f"Blender exited while starting. See {self.session_dir / 'blender.log'}")
                if time.time() > deadline:
                    raise BlenderError(f"Blender did not respond on port {port} within 90 seconds.")
                time.sleep(0.3)
        connection.settimeout(1800)
        self.stream = connection.makefile("rwb")

    def call(self, cmd, **args):
        args = {key: value for key, value in args.items() if value is not None}
        with self.lock:
            if self.stream is None or (self.process and self.process.poll() is not None):
                self._start()
            try:
                self.stream.write(json.dumps({"cmd": cmd, "args": args}).encode() + b"\n")
                self.stream.flush()
                line = self.stream.readline()
            except OSError as exc:
                self.stream = None
                raise BlenderError(f"Lost the connection to Blender ({exc}). Call the tool again to restart it.")
            if not line:
                self.stream = None
                raise BlenderError("Blender closed unexpectedly. Call the tool again to restart it.")
        reply = json.loads(line)
        if not reply["ok"]:
            detail = reply["error"]
            if cmd in ("run_python", "raw_python"):
                detail += "\n" + reply.get("traceback", "")
            raise BlenderError(detail)
        return reply["result"]

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
