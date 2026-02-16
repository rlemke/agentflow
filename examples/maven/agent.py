#!/usr/bin/env python3
"""Maven Build Lifecycle Agent — handles Maven build pipeline event tasks.

This agent polls for event tasks across all Maven namespaces:
- maven.resolve: dependency resolution (ResolveDependencies, DownloadArtifact, AnalyzeDependencyTree)
- maven.build: build lifecycle (CompileProject, RunUnitTests, PackageArtifact, GenerateJavadoc)
- maven.publish: artifact publishing (DeployToRepository, PublishSnapshot, PromoteRelease)
- maven.quality: quality analysis (CheckstyleAnalysis, DependencyCheck)

Usage:
    PYTHONPATH=. python examples/maven/agent.py

For Docker/MongoDB mode, set environment variables:
    AFL_MONGODB_URL=mongodb://localhost:27017
    AFL_MONGODB_DATABASE=afl

Tri-mode operation:
    Default:                AgentPoller (polling mode)
    AFL_USE_REGISTRY=1:     RegistryRunner (database-driven)
    AFL_USE_MAVEN_RUNNER=1: MavenArtifactRunner (JVM subprocess execution)
"""

import os
import signal

from handlers import register_all_handlers

from afl.runtime import Evaluator, MemoryStore, Telemetry

USE_REGISTRY = os.environ.get("AFL_USE_REGISTRY", "").strip() == "1"
USE_MAVEN_RUNNER = os.environ.get("AFL_USE_MAVEN_RUNNER", "").strip() == "1"


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
    """Start the Maven build lifecycle agent."""
    store = _make_store()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    if USE_MAVEN_RUNNER:
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

    elif USE_REGISTRY:
        from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig
        from handlers import register_all_registry_handlers

        topics_env = os.environ.get("AFL_RUNNER_TOPICS", "")
        topics = [t.strip() for t in topics_env.split(",") if t.strip()] if topics_env else []

        config = RegistryRunnerConfig(
            service_name="maven-agent",
            server_group="maven",
            poll_interval_ms=2000,
            max_concurrent=5,
            topics=topics,
        )

        runner = RegistryRunner(persistence=store, evaluator=evaluator, config=config)
        register_all_registry_handlers(runner)

        def shutdown(signum, frame):
            print("\nShutting down...")
            runner.stop()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        if topics:
            print(f"Topic filter: {topics}")
        print("Maven agent started (RegistryRunner mode). Press Ctrl+C to stop.")
        runner.start()
    else:
        from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

        config = AgentPollerConfig(
            service_name="maven-agent",
            server_group="maven",
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

        print("Maven agent started. Press Ctrl+C to stop.")
        print("Listening for Maven build lifecycle events...")
        poller.start()


if __name__ == "__main__":
    main()
