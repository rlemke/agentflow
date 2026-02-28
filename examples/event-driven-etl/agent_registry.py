"""RegistryRunner entry point for the event-driven ETL example.

Usage:
    PYTHONPATH=. python examples/event-driven-etl/agent_registry.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from handlers import register_all_registry_handlers

from afl.runtime.registry_runner import RegistryRunner


def main() -> None:
    """Start the RegistryRunner with all ETL handlers."""
    runner = RegistryRunner(service_name="event-driven-etl")
    register_all_registry_handlers(runner)
    print(f"ETL RegistryRunner started with {runner.handler_count} handlers")
    runner.run()


if __name__ == "__main__":
    main()
