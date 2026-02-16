"""Jenkins notification event facet handlers.

Handles SlackNotify and EmailNotify event facets from the jenkins.notify
namespace. Each handler simulates a notification operation with realistic
output.
"""

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

NAMESPACE = "jenkins.notify"


def _slack_notify_handler(payload: dict) -> dict[str, Any]:
    """Send a Slack notification."""
    channel = payload.get("channel", "#general")
    message = payload.get("message", "")
    return {
        "sent": True,
        "timestamp": "1708100000.000100",
    }


def _email_notify_handler(payload: dict) -> dict[str, Any]:
    """Send an email notification."""
    recipients = payload.get("recipients", "")
    subject = payload.get("subject", "")
    return {
        "sent": True,
        "message_id": "<20240216120000.ABC123@jenkins.example.com>",
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.SlackNotify": _slack_notify_handler,
    f"{NAMESPACE}.EmailNotify": _email_notify_handler,
}


def handle(payload: dict) -> dict:
    """RegistryRunner dispatch entrypoint."""
    facet_name = payload["_facet_name"]
    handler = _DISPATCH.get(facet_name)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet_name}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register all facets with a RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_notify_handlers(poller) -> None:
    """Register all notify event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered notify handler: %s", fqn)
