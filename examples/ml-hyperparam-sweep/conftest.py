"""Root conftest for ml-hyperparam-sweep — cross-example module isolation."""

import os
import sys

import _pytest.python

_EXAMPLE_ROOT = os.path.dirname(os.path.abspath(__file__))


def _ensure_sweep_handlers():
    for key in list(sys.modules.keys()):
        if key == "handlers" or key.startswith("handlers."):
            mod = sys.modules[key]
            mod_file = getattr(mod, "__file__", "") or ""
            if "ml-hyperparam-sweep" not in mod_file:
                del sys.modules[key]
    if _EXAMPLE_ROOT in sys.path:
        sys.path.remove(_EXAMPLE_ROOT)
    sys.path.insert(0, _EXAMPLE_ROOT)


_ensure_sweep_handlers()

_original_importtestmodule = _pytest.python.importtestmodule


def _patched_importtestmodule(path, config):
    if "ml-hyperparam-sweep" in str(path):
        _ensure_sweep_handlers()
    return _original_importtestmodule(path, config)


_pytest.python.importtestmodule = _patched_importtestmodule
