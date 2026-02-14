#!/usr/bin/env python3
"""Run LZ pipeline for a single region — smoke test / standalone mode.

Uses MemoryStore (no MongoDB needed). Registers just the handler modules
needed for a single region LZ build.

Usage:
    cd examples/continental-lz
    PYTHONPATH=../.. python scripts/run_region.py --region Belgium --output-dir /tmp/lz-belgium

Regions correspond to osm.geo.cache.Europe.<Region> facet names.
For North America: UnitedStates, Canada
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure afl package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
# Ensure handlers are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from afl.parser import parse
from afl.validator import validate
from afl.emitter import emit_dict
from afl.runtime import Evaluator, MemoryStore, Telemetry
from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig


# Mapping of region names to (cache namespace, GH namespace) pairs
REGION_MAP = {
    # Europe
    "Germany": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "France": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "UnitedKingdom": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Spain": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Italy": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Poland": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Netherlands": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Belgium": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Switzerland": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Austria": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Sweden": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    "Norway": ("osm.geo.cache.Europe", "osm.geo.cache.GraphHopper.Europe"),
    # North America
    "UnitedStates": ("osm.geo.cache.NorthAmerica", "osm.geo.cache.GraphHopper.NorthAmerica"),
    "Canada": ("osm.geo.cache.NorthAmerica", "osm.geo.cache.GraphHopper.NorthAmerica"),
}


def build_single_region_afl(region: str, output_dir: str) -> str:
    """Generate AFL source for a single-region LZ pipeline."""
    cache_ns, gh_ns = REGION_MAP[region]
    return f"""
// Auto-generated single-region LZ workflow
namespace single.region {{
    use osm.types
    uses {cache_ns}
    uses {gh_ns}
    uses osm.geo.Roads.ZoomBuilder

    workflow Build{region}LZ(output_dir: String = "{output_dir}") => (
        total_edges: Long,
        selected_edges: Long
    ) andThen {{
        osm = {cache_ns}.{region}()
        gh = {gh_ns}.{region}(cache = osm.cache)
        lz = osm.geo.Roads.ZoomBuilder.BuildZoomLayers(
            cache = osm.cache,
            graph = gh.graph,
            min_population = 20000,
            output_dir = $.output_dir
        )
        yield Build{region}LZ(
            total_edges = lz.result,
            selected_edges = lz.metrics
        )
    }}
}}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LZ pipeline for a single region")
    parser.add_argument(
        "--region",
        required=True,
        choices=sorted(REGION_MAP.keys()),
        help="Region name (e.g., Belgium, Germany, UnitedStates)",
    )
    parser.add_argument(
        "--output-dir",
        default="/tmp/lz-output",
        help="Output directory for LZ results (default: /tmp/lz-output)",
    )
    args = parser.parse_args()

    print(f"Building LZ pipeline for: {args.region}")
    print(f"Output directory: {args.output_dir}")

    # Read base AFL sources
    osm_afl_dir = Path(__file__).resolve().parent.parent.parent / "osm-geocoder" / "afl"
    base_files = [
        osm_afl_dir / "osmtypes.afl",
        osm_afl_dir / "osmoperations.afl",
        osm_afl_dir / "osmcache.afl",
        osm_afl_dir / "osmgraphhopper.afl",
        osm_afl_dir / "osmgraphhoppercache.afl",
        osm_afl_dir / "osmzoombuilder.afl",
        osm_afl_dir / "osmfilters_population.afl",
    ]

    sources = ""
    for f in base_files:
        if not f.exists():
            print(f"ERROR: Missing AFL source: {f}")
            sys.exit(1)
        sources += f.read_text() + "\n"

    # Add single-region workflow
    sources += build_single_region_afl(args.region, args.output_dir)

    # Parse and validate
    print("Compiling AFL sources...")
    ast = parse(sources)
    result = validate(ast)
    if not result.is_valid:
        print(f"Validation errors: {result.errors}")
        sys.exit(1)
    print("Validation passed")

    compiled = emit_dict(ast)
    wf_name = f"single.region.Build{args.region}LZ"
    print(f"Workflow: {wf_name}")

    # Set up runtime
    store = MemoryStore()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    config = RegistryRunnerConfig(
        service_name="continental-lz-single",
        server_group="continental",
        poll_interval_ms=1000,
        max_concurrent=2,
    )

    runner = RegistryRunner(persistence=store, evaluator=evaluator, config=config)

    # Register handlers
    from handlers.cache_handlers import register_handlers as reg_cache
    from handlers.operations_handlers import register_handlers as reg_operations
    from handlers.graphhopper_handlers import register_handlers as reg_graphhopper
    from handlers.population_handlers import register_handlers as reg_population
    from handlers.zoom_handlers import register_handlers as reg_zoom

    reg_cache(runner)
    reg_operations(runner)
    reg_graphhopper(runner)
    reg_population(runner)
    reg_zoom(runner)

    print(f"Starting LZ pipeline for {args.region}...")
    print("Press Ctrl+C to stop.")

    import signal

    def shutdown(signum, frame):
        print("\nShutting down...")
        runner.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    runner.start()


if __name__ == "__main__":
    main()
