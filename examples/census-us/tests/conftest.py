"""Conftest for census-us tests.

Adds the census-us example root to sys.path so that
``from handlers.xxx import ...`` works from the test location.
"""

import os
import sys

import pytest

# examples/census-us/tests/ → examples/census-us/
_EXAMPLE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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


# Purge at collection time so module-level imports in test files work
_ensure_census_handlers()


@pytest.fixture(autouse=True)
def _census_handlers_on_path():
    """Ensure census-us handlers are on sys.path before each test."""
    _ensure_census_handlers()
