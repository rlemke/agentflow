#!/usr/bin/env python3
"""Continental LZ Pipeline Agent — RegistryRunner mode.

Registers the subset of handlers needed for the LZ road infrastructure
and GTFS transit analysis pipelines across US, Canada, and Europe.

Handler modules reused from examples/osm-geocoder/handlers/:
  - cache_handlers:       ~250 region cache facets (OSM PBF downloads)
  - operations_handlers:  13 operations (download orchestration)
  - graphhopper_handlers: ~200 GraphHopper facets (routing graph builds)
  - population_handlers:  11 population facets (LZ anchor cities)
  - zoom_handlers:        9 zoom builder facets (LZ pipeline stages)
  - gtfs_handlers:        12 GTFS facets (transit analysis)

Usage:
    AFL_USE_REGISTRY=1 AFL_MONGODB_URL=mongodb://localhost:27017 \\
        PYTHONPATH=../.. python agent.py

For Docker mode, environment is configured via docker-compose.yml.
"""

import os
import signal
import sys

from afl.runtime import Evaluator, MemoryStore, Telemetry
from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig


def _make_store():
    """Create a persistence store from environment configuration."""
    mongodb_url = os.environ.get("AFL_MONGODB_URL")
    mongodb_database = os.environ.get("AFL_MONGODB_DATABASE", "afl_continental_lz")

    if mongodb_url:
        from afl.runtime.mongo_store import MongoStore

        print(f"Using MongoDB: {mongodb_url}/{mongodb_database}")
        return MongoStore(connection_string=mongodb_url, database_name=mongodb_database)

    print("Using in-memory store (set AFL_MONGODB_URL for MongoDB)")
    return MemoryStore()


def main() -> None:
    """Start the Continental LZ agent."""
    store = _make_store()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    topics_env = os.environ.get("AFL_RUNNER_TOPICS", "")
    topics = [t.strip() for t in topics_env.split(",") if t.strip()] if topics_env else []

    config = RegistryRunnerConfig(
        service_name="continental-lz",
        server_group="continental",
        poll_interval_ms=2000,
        max_concurrent=4,  # GraphHopper is memory-intensive
        topics=topics,
    )

    runner = RegistryRunner(persistence=store, evaluator=evaluator, config=config)

    # Register only the handler modules needed for LZ + GTFS pipelines
    from handlers.cache_handlers import register_handlers as reg_cache
    from handlers.operations_handlers import register_handlers as reg_operations
    from handlers.graphhopper_handlers import register_handlers as reg_graphhopper
    from handlers.population_handlers import register_handlers as reg_population
    from handlers.zoom_handlers import register_handlers as reg_zoom
    from handlers.gtfs_handlers import register_handlers as reg_gtfs

    reg_cache(runner)
    reg_operations(runner)
    reg_graphhopper(runner)
    reg_population(runner)
    reg_zoom(runner)
    reg_gtfs(runner)

    def shutdown(signum, frame):
        print("\nShutting down...")
        runner.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    if topics:
        print(f"Topic filter: {topics}")
    print("Continental LZ agent started (RegistryRunner mode). Press Ctrl+C to stop.")
    print("Handling: cache, operations, graphhopper, population, zoom, gtfs")
    runner.start()


if __name__ == "__main__":
    main()
