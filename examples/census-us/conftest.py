"""Root conftest for census-us example.

Ensures that the census-us handlers package is active when tests in this
example tree are collected or run.  Other examples (osm-geocoder, etc.)
may load their own ``handlers`` package first; this conftest purges those
stale entries from ``sys.modules`` so that subsequent imports resolve to the
census-us handlers.
"""

import os
import sys

import _pytest.python

_EXAMPLE_ROOT = os.path.dirname(os.path.abspath(__file__))


def _ensure_census_handlers():
    """Purge stale handlers and ensure census-us handlers are active."""
    for key in list(sys.modules.keys()):
        if key == "handlers" or key.startswith("handlers."):
            mod = sys.modules[key]
            mod_file = getattr(mod, "__file__", "") or ""
            if "census-us" not in mod_file:
                del sys.modules[key]
    if _EXAMPLE_ROOT in sys.path:
        sys.path.remove(_EXAMPLE_ROOT)
    sys.path.insert(0, _EXAMPLE_ROOT)


# Purge at conftest load time.
_ensure_census_handlers()

# ---------------------------------------------------------------------------
# Monkey-patch importtestmodule to purge stale handlers right before each
# census-us module is imported by pytest.
# ---------------------------------------------------------------------------
_original_importtestmodule = _pytest.python.importtestmodule


def _patched_importtestmodule(path, config):
    if "census-us" in str(path):
        _ensure_census_handlers()
    return _original_importtestmodule(path, config)


_pytest.python.importtestmodule = _patched_importtestmodule
