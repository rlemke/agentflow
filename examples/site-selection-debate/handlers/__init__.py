"""Site-Selection Debate handlers -- registration aggregator."""

from __future__ import annotations

from .spatial.spatial_handlers import register_spatial_handlers
from .research.research_handlers import register_research_handlers
from .debate.debate_handlers import register_debate_handlers
from .synthesis.synthesis_handlers import register_synthesis_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_spatial_handlers(poller)
    register_research_handlers(poller)
    register_debate_handlers(poller)
    register_synthesis_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .spatial.spatial_handlers import register_handlers as reg_spatial
    from .research.research_handlers import register_handlers as reg_research
    from .debate.debate_handlers import register_handlers as reg_debate
    from .synthesis.synthesis_handlers import register_handlers as reg_synthesis

    reg_spatial(runner)
    reg_research(runner)
    reg_debate(runner)
    reg_synthesis(runner)
