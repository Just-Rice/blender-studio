"""Command registry. Each command is a plain function taking JSON-friendly keyword arguments."""
import importlib

from . import state

_registry = {}


def command(mutates=True):
    def wrap(fn):
        _registry[fn.__name__] = (fn, mutates)
        return fn
    return wrap


def load_all():
    for name in ("scene", "lighting", "materials", "camera", "polish", "look", "render", "check", "assets",
                 "sculpt", "character", "human", "animate"):
        importlib.import_module(f".ops.{name}", __package__)


def dispatch(name, args):
    if name not in _registry:
        raise ValueError(f"Unknown command '{name}'. Available: {', '.join(sorted(_registry))}")
    fn, mutates = _registry[name]
    if not mutates:
        return fn(**args)
    state.checkpoint(name)
    try:
        return fn(**args)
    except Exception:
        # A failed change must not leave a half-built scene behind.
        state.undo(1)
        raise


@command(mutates=False)
def undo(steps=1):
    return state.undo(steps)
