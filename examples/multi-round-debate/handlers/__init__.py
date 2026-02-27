"""Multi-Round Debate handlers -- registration aggregator."""

from __future__ import annotations

from .setup.setup_handlers import register_setup_handlers
from .argumentation.argumentation_handlers import register_argumentation_handlers
from .scoring.scoring_handlers import register_scoring_handlers
from .synthesis.synthesis_handlers import register_synthesis_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_setup_handlers(poller)
    register_argumentation_handlers(poller)
    register_scoring_handlers(poller)
    register_synthesis_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .setup.setup_handlers import register_handlers as reg_setup
    from .argumentation.argumentation_handlers import register_handlers as reg_argumentation
    from .scoring.scoring_handlers import register_handlers as reg_scoring
    from .synthesis.synthesis_handlers import register_handlers as reg_synthesis

    reg_setup(runner)
    reg_argumentation(runner)
    reg_scoring(runner)
    reg_synthesis(runner)
