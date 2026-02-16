"""AWS Lambda + Step Functions pipeline handlers."""

from .lambda_handlers import register_lambda_handlers
from .stepfunctions_handlers import register_stepfunctions_handlers

__all__ = [
    "register_all_handlers",
    "register_all_registry_handlers",
    "register_lambda_handlers",
    "register_stepfunctions_handlers",
]


def register_all_handlers(poller) -> None:
    """Register all AWS event facet handlers with the given poller."""
    register_lambda_handlers(poller)
    register_stepfunctions_handlers(poller)


def register_all_registry_handlers(runner) -> None:
    """Register all AWS event facet handlers with a RegistryRunner."""
    from .lambda_handlers import register_handlers as reg_lambda
    from .stepfunctions_handlers import register_handlers as reg_sfn

    reg_lambda(runner)
    reg_sfn(runner)
