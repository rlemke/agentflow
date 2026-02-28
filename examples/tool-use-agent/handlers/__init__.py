"""Tool-Use Agent handlers -- registration aggregator."""

from __future__ import annotations

from .compute.compute_handlers import register_compute_handlers
from .output.output_handlers import register_output_handlers
from .planning.planning_handlers import register_planning_handlers
from .search.search_handlers import register_search_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_planning_handlers(poller)
    register_search_handlers(poller)
    register_compute_handlers(poller)
    register_output_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .compute.compute_handlers import register_handlers as reg_compute
    from .output.output_handlers import register_handlers as reg_output
    from .planning.planning_handlers import register_handlers as reg_planning
    from .search.search_handlers import register_handlers as reg_search

    reg_planning(runner)
    reg_search(runner)
    reg_compute(runner)
    reg_output(runner)
