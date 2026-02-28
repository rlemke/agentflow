"""Site-Selection Debate handlers -- registration aggregator."""

from __future__ import annotations

from .debate.debate_handlers import register_debate_handlers
from .research.research_handlers import register_research_handlers
from .spatial.spatial_handlers import register_spatial_handlers
from .synthesis.synthesis_handlers import register_synthesis_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_spatial_handlers(poller)
    register_research_handlers(poller)
    register_debate_handlers(poller)
    register_synthesis_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .debate.debate_handlers import register_handlers as reg_debate
    from .research.research_handlers import register_handlers as reg_research
    from .spatial.spatial_handlers import register_handlers as reg_spatial
    from .synthesis.synthesis_handlers import register_handlers as reg_synthesis

    reg_spatial(runner)
    reg_research(runner)
    reg_debate(runner)
    reg_synthesis(runner)
