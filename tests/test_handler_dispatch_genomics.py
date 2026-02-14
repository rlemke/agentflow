"""Tests for genomics handler dispatch adapter pattern.

Verifies that each genomics handler module's handle() function dispatches correctly
using the _facet_name key, that _DISPATCH dicts have the expected keys,
and that register_handlers() calls runner.register_handler the expected
number of times.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

GENOMICS_DIR = str(Path(__file__).parent.parent / "examples" / "genomics")


def _genomics_import(module_name: str):
    """Import a genomics handlers submodule, ensuring correct sys.path."""
    if GENOMICS_DIR in sys.path:
        sys.path.remove(GENOMICS_DIR)
    sys.path.insert(0, GENOMICS_DIR)

    full_name = f"handlers.{module_name}"

    # If module is already loaded from the right location, return it
    if full_name in sys.modules:
        mod = sys.modules[full_name]
        mod_file = getattr(mod, "__file__", "")
        if mod_file and "genomics" in mod_file:
            return mod
        del sys.modules[full_name]

    # Ensure the handlers package itself is from genomics
    if "handlers" in sys.modules:
        pkg = sys.modules["handlers"]
        pkg_file = getattr(pkg, "__file__", "")
        if pkg_file and "genomics" not in pkg_file:
            stale = [k for k in sys.modules if k == "handlers" or k.startswith("handlers.")]
            for k in stale:
                del sys.modules[k]

    return importlib.import_module(full_name)


class TestGenomicsHandlers:
    def test_dispatch_keys(self):
        mod = _genomics_import("genomics_handlers")
        assert len(mod._DISPATCH) == 9
        assert "genomics.Facets.IngestReference" in mod._DISPATCH
        assert "genomics.Facets.Publish" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _genomics_import("genomics_handlers")
        result = mod.handle({"_facet_name": "genomics.Facets.IngestReference", "reference_build": "GRCh38"})
        assert isinstance(result, dict)
        assert "result" in result

    def test_handle_unknown_facet(self):
        mod = _genomics_import("genomics_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "genomics.Facets.NonExistent"})

    def test_register_handlers(self):
        mod = _genomics_import("genomics_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == len(mod._DISPATCH)


class TestGenomicsCacheHandlers:
    def test_dispatch_keys(self):
        mod = _genomics_import("cache_handlers")
        assert len(mod._DISPATCH) == 17
        assert "genomics.cache.reference.GRCh38" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _genomics_import("cache_handlers")
        result = mod.handle({"_facet_name": "genomics.cache.reference.GRCh38"})
        assert isinstance(result, dict)
        assert "cache" in result

    def test_register_handlers(self):
        mod = _genomics_import("cache_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == len(mod._DISPATCH)


class TestGenomicsResolveHandlers:
    def test_dispatch_keys(self):
        mod = _genomics_import("resolve_handlers")
        assert len(mod._DISPATCH) == 4
        assert "genomics.cache.Resolve.ResolveReference" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _genomics_import("resolve_handlers")
        result = mod.handle({"_facet_name": "genomics.cache.Resolve.ListResources"})
        assert isinstance(result, dict)
        assert "result" in result

    def test_register_handlers(self):
        mod = _genomics_import("resolve_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == len(mod._DISPATCH)


class TestGenomicsIndexHandlers:
    def test_dispatch_keys(self):
        mod = _genomics_import("index_handlers")
        assert len(mod._DISPATCH) == 10
        assert "genomics.cache.index.bwa.GRCh38" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _genomics_import("index_handlers")
        result = mod.handle({"_facet_name": "genomics.cache.index.bwa.GRCh38"})
        assert isinstance(result, dict)
        assert "index" in result

    def test_register_handlers(self):
        mod = _genomics_import("index_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == len(mod._DISPATCH)


class TestGenomicsOperationsHandlers:
    def test_dispatch_keys(self):
        mod = _genomics_import("operations_handlers")
        assert len(mod._DISPATCH) == 5
        assert "genomics.cache.Operations.Download" in mod._DISPATCH

    def test_handle_dispatches(self):
        mod = _genomics_import("operations_handlers")
        result = mod.handle({"_facet_name": "genomics.cache.Operations.Download"})
        assert isinstance(result, dict)

    def test_handle_unknown_facet(self):
        mod = _genomics_import("operations_handlers")
        with pytest.raises(ValueError, match="Unknown facet"):
            mod.handle({"_facet_name": "genomics.cache.Operations.Bogus"})

    def test_register_handlers(self):
        mod = _genomics_import("operations_handlers")
        runner = MagicMock()
        mod.register_handlers(runner)
        assert runner.register_handler.call_count == len(mod._DISPATCH)


class TestGenomicsInitRegistryHandlers:
    def test_register_all_registry_handlers(self):
        mod = _genomics_import("__init__")
        runner = MagicMock()
        mod.register_all_registry_handlers(runner)
        # 9 genomics + 17 cache + 4 resolve + 10 index + 5 operations = 45
        assert runner.register_handler.call_count == 45
