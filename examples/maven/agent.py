#!/usr/bin/env python3
"""Maven Artifact Runner Agent — executes JVM programs packaged as Maven artifacts.

Usage:
    PYTHONPATH=. python examples/maven/agent.py

For Docker/MongoDB mode, set environment variables:
    AFL_MONGODB_URL=mongodb://localhost:27017
    AFL_MONGODB_DATABASE=afl
"""

import os
import signal

from afl.runtime import Evaluator, MemoryStore, Telemetry


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
    """Start the Maven artifact runner agent."""
    store = _make_store()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    from maven_runner import MavenArtifactRunner, MavenRunnerConfig

    topics_env = os.environ.get("AFL_RUNNER_TOPICS", "")
    topics = [t.strip() for t in topics_env.split(",") if t.strip()] if topics_env else []

    config = MavenRunnerConfig(
        service_name="maven-agent",
        server_group="maven",
        poll_interval_ms=2000,
        max_concurrent=5,
        topics=topics,
        repository_url=os.environ.get(
            "AFL_MAVEN_REPOSITORY", "https://repo1.maven.org/maven2"
        ),
        cache_dir=os.environ.get("AFL_MAVEN_CACHE", ""),
        java_command=os.environ.get("AFL_JAVA_COMMAND", "java"),
    )

    runner = MavenArtifactRunner(
        persistence=store, evaluator=evaluator, config=config
    )

    def shutdown(signum, frame):
        print("\nShutting down...")
        runner.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    if topics:
        print(f"Topic filter: {topics}")
    print("Maven agent started (MavenArtifactRunner mode). Press Ctrl+C to stop.")
    print("Register mvn: handlers to execute JVM subprocesses.")
    runner.start()


if __name__ == "__main__":
    main()
