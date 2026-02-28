"""Data Quality Pipeline handlers -- registration aggregator."""

from __future__ import annotations

from .profiling.profiling_handlers import register_profiling_handlers
from .remediation.remediation_handlers import register_remediation_handlers
from .scoring.scoring_handlers import register_scoring_handlers
from .validation.validation_handlers import register_validation_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_profiling_handlers(poller)
    register_validation_handlers(poller)
    register_scoring_handlers(poller)
    register_remediation_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .profiling.profiling_handlers import register_handlers as reg_profiling
    from .remediation.remediation_handlers import register_handlers as reg_remediation
    from .scoring.scoring_handlers import register_handlers as reg_scoring
    from .validation.validation_handlers import register_handlers as reg_validation

    reg_profiling(runner)
    reg_validation(runner)
    reg_scoring(runner)
    reg_remediation(runner)
