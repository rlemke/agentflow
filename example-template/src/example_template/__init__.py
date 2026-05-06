"""Standalone Facetwork example — registered via the ``facetwork.examples``
entry point. Copy this directory to a new repo, rename ``example_template``
to your example's import name, and adjust ``pyproject.toml`` accordingly.
"""

from __future__ import annotations

from pathlib import Path

from facetwork.examples import ExamplePackage

from .handlers import register_all_registry_handlers

example = ExamplePackage(
    name="example-template",
    ffl_dir=Path(__file__).parent / "ffl",
    register_handlers=register_all_registry_handlers,
)
