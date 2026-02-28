"""Monte Carlo risk analysis handlers package.

Provides registration functions for all risk event facet handlers,
supporting both AgentPoller and RegistryRunner execution models.
"""

from .analytics.analytics_handlers import register_analytics_handlers
from .market_data.market_handlers import register_market_data_handlers
from .reporting.report_handlers import register_reporting_handlers
from .simulation.simulation_handlers import register_simulation_handlers

__all__ = [
    "register_all_handlers",
    "register_all_registry_handlers",
    "register_market_data_handlers",
    "register_simulation_handlers",
    "register_analytics_handlers",
    "register_reporting_handlers",
]


def register_all_handlers(poller) -> None:
    """Register all event facet handlers with the given poller."""
    register_market_data_handlers(poller)
    register_simulation_handlers(poller)
    register_analytics_handlers(poller)
    register_reporting_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all facet handlers with a RegistryRunner."""
    from .analytics.analytics_handlers import register_handlers as reg_analytics
    from .market_data.market_handlers import register_handlers as reg_market
    from .reporting.report_handlers import register_handlers as reg_reporting
    from .simulation.simulation_handlers import register_handlers as reg_sim

    reg_market(runner)
    reg_sim(runner)
    reg_analytics(runner)
    reg_reporting(runner)
