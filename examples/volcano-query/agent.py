#!/usr/bin/env python3
"""Volcano Query Agent — handles atomic volcano data pipeline events.

This agent polls for event tasks in the volcano namespace:
- volcano.LoadVolcanoData: load the full volcano dataset
- volcano.FilterByRegion: filter volcanoes by state
- volcano.FilterByElevation: filter volcanoes by minimum elevation
- volcano.FormatVolcanoes: format volcano data for display
- volcano.RenderMap: generate HTML map of volcanoes

Uses a built-in dataset of ~30 notable US volcanoes (no external API required).

Usage:
    PYTHONPATH=. python examples/volcano-query/agent.py

For Docker/MongoDB mode, set environment variables:
    AFL_MONGODB_URL=mongodb://localhost:27017
    AFL_MONGODB_DATABASE=afl
"""

import os
import signal

from handlers import register_all_handlers

from afl.runtime import Evaluator, MemoryStore, Telemetry
from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig


def main() -> None:
    """Start the volcano query agent."""
    mongodb_url = os.environ.get("AFL_MONGODB_URL")
    mongodb_database = os.environ.get("AFL_MONGODB_DATABASE", "afl")

    if mongodb_url:
        from afl.runtime.mongo_store import MongoStore

        print(f"Using MongoDB: {mongodb_url}/{mongodb_database}")
        store = MongoStore(connection_string=mongodb_url, database_name=mongodb_database)
    else:
        print("Using in-memory store (set AFL_MONGODB_URL for MongoDB)")
        store = MemoryStore()

    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    config = AgentPollerConfig(
        service_name="volcano-query",
        server_group="volcano",
        poll_interval_ms=2000,
        max_concurrent=5,
    )

    poller = AgentPoller(persistence=store, evaluator=evaluator, config=config)

    register_all_handlers(poller)

    def shutdown(signum, frame):
        print("\nShutting down...")
        poller.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print("Volcano Query agent started. Press Ctrl+C to stop.")
    print("Listening for volcano.LoadVolcanoData, volcano.FilterByRegion,")
    print("  volcano.FilterByElevation, volcano.FormatVolcanoes, volcano.RenderMap events...")
    poller.start()


if __name__ == "__main__":
    main()
