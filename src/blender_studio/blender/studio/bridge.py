"""Socket bridge. Accepts one JSON command per line and runs it on Blender's main thread."""
import argparse
import json
import os
import queue
import socket
import sys
import threading
import traceback

import bpy

from . import commands, state

_requests = queue.Queue()


def _client_thread(conn):
    with conn, conn.makefile("rwb") as stream:
        for line in stream:
            if not line.strip():
                continue
            reply = queue.Queue(1)
            _requests.put((line, reply))
            stream.write(reply.get() + b"\n")
            stream.flush()


def _accept_loop(server):
    while True:
        conn, _ = server.accept()
        threading.Thread(target=_client_thread, args=(conn,), daemon=True).start()


def _handle(line):
    try:
        request = json.loads(line)
        result = commands.dispatch(request["cmd"], request.get("args") or {})
        response = {"ok": True, "result": result}
    except Exception as exc:
        response = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=6),
        }
    return json.dumps(response, default=str).encode()


def _pump_timer():
    """GUI mode: drain pending commands from a main-thread timer."""
    while True:
        try:
            line, reply = _requests.get_nowait()
        except queue.Empty:
            return 0.05
        reply.put(_handle(line))


def _exit_when_parent_closes():
    """The launcher keeps our stdin open; when it goes away, so do we (works on every OS)."""
    try:
        sys.stdin.buffer.read()
    except Exception:
        pass
    os._exit(0)


def _serve_blocking():
    """Background mode: this script owns the main thread, so loop here."""
    while True:
        line, reply = _requests.get()
        reply.put(_handle(line))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9877)
    parser.add_argument("--watch-stdin", action="store_true")
    parser.add_argument("--keep-startup-scene", action="store_true")
    parser.add_argument("--session-dir", default="")
    args = parser.parse_args(argv)

    state.init(args.session_dir)
    commands.load_all()
    if not args.keep_startup_scene:
        commands.dispatch("new_scene", {})

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", args.port))
    server.listen(4)
    threading.Thread(target=_accept_loop, args=(server,), daemon=True).start()
    print(f"[blender-studio] READY on 127.0.0.1:{args.port}", flush=True)

    if args.watch_stdin:
        threading.Thread(target=_exit_when_parent_closes, daemon=True).start()
    if bpy.app.background:
        _serve_blocking()
    else:
        bpy.app.timers.register(_pump_timer, persistent=True)
