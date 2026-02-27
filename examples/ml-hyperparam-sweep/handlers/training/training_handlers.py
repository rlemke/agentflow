"""Training handlers — TrainModel."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.ml_utils import train_model_stub

NAMESPACE = "ml.Training"


def handle_train_model(params: dict[str, Any]) -> dict[str, Any]:
    """Handle TrainModel event facet."""
    dataset_name = params.get("dataset_name", "synthetic")
    hyperparams = params.get("hyperparams", {})
    if isinstance(hyperparams, str):
        hyperparams = json.loads(hyperparams)

    model_config = params.get("model_config", {})
    if isinstance(model_config, str):
        model_config = json.loads(model_config)

    run_label = params.get("run_label", "run")

    result = train_model_stub(
        dataset_info={"name": dataset_name},
        hyperparams=hyperparams,
        model_config=model_config,
        run_label=run_label,
    )

    step_log = params.get("_step_log")
    if step_log:
        step_log.append({"message": f"Trained model '{result['model_id']}': loss={result['final_loss']:.4f}, acc={result['accuracy']:.4f}", "level": "success"})

    return {"result": result}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.TrainModel": handle_train_model,
}


def handle(payload: dict) -> dict:
    """RegistryRunner entrypoint."""
    facet = payload["_facet_name"]
    handler = _DISPATCH[facet]
    return handler(payload)


def register_handlers(runner) -> None:
    """Register with RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_training_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
