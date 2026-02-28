"""ML Hyperparameter Sweep handlers — registration aggregator."""

from __future__ import annotations

from .data.data_handlers import register_data_handlers
from .evaluation.evaluation_handlers import register_evaluation_handlers
from .reporting.report_handlers import register_reporting_handlers
from .training.training_handlers import register_training_handlers


def register_all_handlers(poller) -> None:
    """Register all handlers with an AgentPoller."""
    register_data_handlers(poller)
    register_training_handlers(poller)
    register_evaluation_handlers(poller)
    register_reporting_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all handlers with a RegistryRunner."""
    from .data.data_handlers import register_handlers as reg_data
    from .evaluation.evaluation_handlers import register_handlers as reg_eval
    from .reporting.report_handlers import register_handlers as reg_reporting
    from .training.training_handlers import register_handlers as reg_training

    reg_data(runner)
    reg_training(runner)
    reg_eval(runner)
    reg_reporting(runner)
