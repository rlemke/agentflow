"""Site-Selection Debate -- AgentPoller entry point (legacy/alternative).

For the recommended approach, use agent_registry.py which uses RegistryRunner.

Usage:
    PYTHONPATH=. python examples/site-selection-debate/agent.py
"""

from __future__ import annotations

import sys
import os

# Ensure handlers are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig
from handlers import register_all_handlers


def main() -> None:
    """Start the AgentPoller with all site-selection debate handlers."""
    poller = AgentPoller(config=AgentPollerConfig(service_name="site-selection-debate"))
    register_all_handlers(poller)
    print("Site-selection debate AgentPoller started")
    poller.run()


if __name__ == "__main__":
    main()
