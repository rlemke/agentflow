#!/usr/bin/env python3
"""Jenkins CI/CD Pipeline Agent — handles Jenkins pipeline event tasks.

This agent polls for event tasks across all Jenkins namespaces:
- jenkins.scm: source control operations (GitCheckout, GitMerge)
- jenkins.build: build tools (MavenBuild, GradleBuild, NpmBuild, DockerBuild)
- jenkins.test: testing and quality (RunTests, CodeQuality, SecurityScan)
- jenkins.artifact: artifact management (ArchiveArtifacts, PublishToRegistry, DockerPush)
- jenkins.deploy: deployment (DeployToEnvironment, DeployToK8s, RollbackDeploy)
- jenkins.notify: notifications (SlackNotify, EmailNotify)

Usage:
    PYTHONPATH=. python examples/jenkins/agent.py

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
    """Start the Jenkins CI/CD agent."""
    store = _make_store()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    if USE_REGISTRY:
        from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig
        from handlers import register_all_registry_handlers

        topics_env = os.environ.get("AFL_RUNNER_TOPICS", "")
        topics = [t.strip() for t in topics_env.split(",") if t.strip()] if topics_env else []

        config = RegistryRunnerConfig(
            service_name="jenkins-agent",
            server_group="jenkins",
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
        print("Jenkins agent started (RegistryRunner mode). Press Ctrl+C to stop.")
        runner.start()
    else:
        from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

        config = AgentPollerConfig(
            service_name="jenkins-agent",
            server_group="jenkins",
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

        print("Jenkins agent started. Press Ctrl+C to stop.")
        print("Listening for Jenkins pipeline events...")
        poller.start()


if __name__ == "__main__":
    main()
