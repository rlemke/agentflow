"""Conftest for maven mocked tests."""
import os
import sys

_EXAMPLE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
# Purge any cached handlers package from other examples to avoid conflicts
for _key in list(sys.modules.keys()):
    if _key == "handlers" or _key.startswith("handlers."):
        del sys.modules[_key]

# Ensure our example root is first on sys.path
if _EXAMPLE_ROOT in sys.path:
    sys.path.remove(_EXAMPLE_ROOT)
sys.path.insert(0, _EXAMPLE_ROOT)
