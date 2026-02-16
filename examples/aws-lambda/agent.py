#!/usr/bin/env python3
"""AWS Lambda + Step Functions Agent — handles AWS pipeline event tasks.

This agent polls for event tasks across AWS namespaces:
- aws.lambda: Lambda operations (CreateFunction, InvokeFunction, etc.)
- aws.stepfunctions: Step Functions operations (CreateStateMachine, StartExecution, etc.)

Usage:
    PYTHONPATH=. python examples/aws-lambda/agent.py

For Docker/MongoDB mode, set environment variables:
    AFL_MONGODB_URL=mongodb://localhost:27017
    AFL_MONGODB_DATABASE=afl

For RegistryRunner mode:
    AFL_USE_REGISTRY=1

LocalStack endpoint (default: http://localhost:4566):
    LOCALSTACK_URL=http://localhost:4566
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
    """Start the AWS Lambda + Step Functions agent."""
    store = _make_store()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=True))

    if USE_REGISTRY:
        from afl.runtime.registry_runner import RegistryRunner, RegistryRunnerConfig
        from handlers import register_all_registry_handlers

        topics_env = os.environ.get("AFL_RUNNER_TOPICS", "")
        topics = [t.strip() for t in topics_env.split(",") if t.strip()] if topics_env else []

        config = RegistryRunnerConfig(
            service_name="aws-lambda-agent",
            server_group="aws-lambda",
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
        print("AWS Lambda agent started (RegistryRunner mode). Press Ctrl+C to stop.")
        runner.start()
    else:
        from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

        config = AgentPollerConfig(
            service_name="aws-lambda-agent",
            server_group="aws-lambda",
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

        print("AWS Lambda agent started. Press Ctrl+C to stop.")
        print("Listening for AWS Lambda and Step Functions events...")
        poller.start()


if __name__ == "__main__":
    main()
