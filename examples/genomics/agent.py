#!/usr/bin/env python3
"""Genomics Cohort Analysis Agent — handles bioinformatics processing events.

This agent polls for event tasks across all genomics namespaces:
- genomics.Facets: core pipeline steps (IngestReference, QcReads, etc.)
- genomics.cache.*: reference, annotation, and SRA cache handlers
- genomics.cache.index.*: aligner index builders (bwa, star, bowtie2)
- genomics.cache.Resolve: name-based resource resolution
- genomics.cache.Operations: low-level cache operations

Usage:
    PYTHONPATH=. python examples/genomics/agent.py

For Docker/MongoDB mode, set environment variables:
    AFL_MONGODB_URL=mongodb://localhost:27017
    AFL_MONGODB_DATABASE=afl

For RegistryRunner mode:
    AFL_USE_REGISTRY=1
"""

import os
import signal

from handlers import register_all_handlers

from afl.runtime import Evaluator, MemoryStore, Telemetry

USE_REGISTRY = os.environ.get("AFL_USE_REGISTRY", "").strip() == "1"


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
    """Start the genomics agent."""
    store = _make_store()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    if USE_REGISTRY:
        from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig
        from handlers import register_all_registry_handlers

        config = RegistryRunnerConfig(
            service_name="genomics-agent",
            server_group="genomics",
            poll_interval_ms=2000,
            max_concurrent=5,
        )

        runner = RegistryRunner(persistence=store, evaluator=evaluator, config=config)
        register_all_registry_handlers(runner)

        def shutdown(signum, frame):
            print("\nShutting down...")
            runner.stop()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        print("Genomics agent started (RegistryRunner mode). Press Ctrl+C to stop.")
        runner.start()
    else:
        from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

        config = AgentPollerConfig(
            service_name="genomics-agent",
            server_group="genomics",
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

        print("Genomics agent started. Press Ctrl+C to stop.")
        print("Listening for genomics events...")
        poller.start()


if __name__ == "__main__":
    main()
