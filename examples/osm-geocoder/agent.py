#!/usr/bin/env python3
"""OSM Geocoder Agent — handles geocoding and OSM data processing events.

This agent polls for event tasks across all OSM namespaces:
- osm.geo.Geocode: address geocoding via Nominatim API
- osm.geo.cache.*: ~250 region cache handlers (Geofabrik URLs)
- osm.geo.Operations.*: download, tile, routing graph operations
- osm.geo.POIs.*: point-of-interest extraction

Usage:
    PYTHONPATH=. python examples/osm-geocoder/agent.py

For Docker/MongoDB mode, set environment variables:
    AFL_MONGODB_URL=mongodb://localhost:27017
    AFL_MONGODB_DATABASE=afl

Requires:
    pip install requests
"""

import os
import signal

import requests
from handlers import register_all_handlers

from afl.runtime import Evaluator, MemoryStore, Telemetry
from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

USE_REGISTRY = os.environ.get("AFL_USE_REGISTRY", "").strip() == "1"

# Nominatim API (free, no API key required — please respect usage policy)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AgentFlow-OSM-Example/1.0"


def geocode_handler(payload: dict) -> dict:
    """Handle osm.Geocode event: resolve address to coordinates.

    Args:
        payload: {"address": "some address string"}

    Returns:
        {"result": {"lat": "...", "lon": "...", "display_name": "..."}}

    Raises:
        ValueError: If the address cannot be resolved
    """
    address = payload.get("address", "")
    step_log = payload.get("_step_log")
    if not address:
        raise ValueError("No address provided")

    response = requests.get(
        NOMINATIM_URL,
        params={"q": address, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()

    results = response.json()
    if not results:
        raise ValueError(f"No results found for address: {address}")

    result = results[0]
    if step_log:
        step_log(f"Geocode: '{address}' -> ({result['lat']}, {result['lon']})")
    return {
        "result": {
            "lat": result["lat"],
            "lon": result["lon"],
            "display_name": result["display_name"],
        }
    }


def _make_store():
    """Create a persistence store from environment configuration."""
    mongodb_url = os.environ.get("AFL_MONGODB_URL")
    mongodb_database = os.environ.get("AFL_MONGODB_DATABASE", "afl")

    if mongodb_url:
        from afl.runtime.mongo_store import MongoStore

        print(f"Using MongoDB: {mongodb_url}/{mongodb_database}")
        return MongoStore(connection_string=mongodb_url, database_name=mongodb_database)

    print("Using in-memory store (set AFL_MONGODB_URL for MongoDB)")
    return MemoryStore()


def main() -> None:
    """Start the geocoder agent."""
    store = _make_store()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    if USE_REGISTRY:
        from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig
        from handlers import register_all_registry_handlers

        topics_env = os.environ.get("AFL_RUNNER_TOPICS", "")
        topics = [t.strip() for t in topics_env.split(",") if t.strip()] if topics_env else []

        config = RegistryRunnerConfig(
            service_name="osm-geocoder",
            server_group="osm",
            poll_interval_ms=2000,
            max_concurrent=5,
            topics=topics,
        )

        runner = RegistryRunner(persistence=store, evaluator=evaluator, config=config)

        # Register geocoding handler via dispatch adapter
        runner.register_handler(
            facet_name="osm.geo.Geocode",
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="geocode_handler",
        )

        # Register all OSM handlers
        register_all_registry_handlers(runner)

        def shutdown(signum, frame):
            print("\nShutting down...")
            runner.stop()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        if topics:
            print(f"Topic filter: {topics}")
        print("OSM Geocoder agent started (RegistryRunner mode). Press Ctrl+C to stop.")
        runner.start()
    else:
        config = AgentPollerConfig(
            service_name="osm-geocoder",
            server_group="osm",
            poll_interval_ms=2000,
            max_concurrent=5,
        )

        poller = AgentPoller(persistence=store, evaluator=evaluator, config=config)

        # Register geocoding handler
        poller.register("osm.geo.Geocode", geocode_handler)

        # Register all OSM cache, operations, and POI handlers
        register_all_handlers(poller)

        def shutdown(signum, frame):
            print("\nShutting down...")
            poller.stop()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        print("OSM Geocoder agent started. Press Ctrl+C to stop.")
        print("Listening for osm.geo.Geocode and ~270 OSM data events...")
        poller.start()


if __name__ == "__main__":
    main()
