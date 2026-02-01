#!/usr/bin/env python3
"""OSM Geocoder Agent — handles geocoding and OSM data processing events.

This agent polls for event tasks across all OSM namespaces:
- osm.geo.Geocode: address geocoding via Nominatim API
- osm.geo.cache.*: ~250 region cache handlers (Geofabrik URLs)
- osm.geo.Operations.*: download, tile, routing graph operations
- osm.geo.POIs.*: point-of-interest extraction

Usage:
    PYTHONPATH=. python examples/osm-geocoder/agent.py

Requires:
    pip install requests
"""

import signal

import requests
from handlers import register_all_handlers

from afl.runtime import Evaluator, MemoryStore, Telemetry
from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

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
    return {
        "result": {
            "lat": result["lat"],
            "lon": result["lon"],
            "display_name": result["display_name"],
        }
    }


def main() -> None:
    """Start the geocoder agent."""
    store = MemoryStore()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    config = AgentPollerConfig(
        service_name="osm-geocoder",
        server_group="osm",
        poll_interval_ms=2000,
        max_concurrent=3,  # respect Nominatim rate limits
    )

    poller = AgentPoller(persistence=store, evaluator=evaluator, config=config)

    # Register geocoding handler
    poller.register("osm.geo.Geocode", geocode_handler)

    # Register all OSM cache, operations, and POI handlers
    register_all_handlers(poller)

    # Graceful shutdown on SIGTERM/SIGINT
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
