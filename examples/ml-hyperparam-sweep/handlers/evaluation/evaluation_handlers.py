"""Evaluation handlers — EvaluateModel, CompareToBestModel."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.ml_utils import compare_results, evaluate_model_stub

NAMESPACE = "ml.Evaluation"


def handle_evaluate_model(params: dict[str, Any]) -> dict[str, Any]:
    """Handle EvaluateModel event facet."""
    model_id = params.get("model_id", "")
    test_path = params.get("test_path", "/data/splits/test.csv")

    result = evaluate_model_stub(model_id=model_id, test_path=test_path)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append({"message": f"Evaluated model '{model_id}': f1={result['f1_score']:.4f}", "level": "success"})

    return {"result": result}


def handle_compare_to_best(params: dict[str, Any]) -> dict[str, Any]:
    """Handle CompareToBestModel event facet."""
    eval_results = params.get("eval_results", [])
    if isinstance(eval_results, str):
        eval_results = json.loads(eval_results)

    metric_name = params.get("metric_name", "f1_score")

    comparison = compare_results(eval_results=eval_results, metric_name=metric_name)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append({"message": f"Best model: {comparison['best_model_id']} ({metric_name})", "level": "success"})

    return {"comparison": comparison}


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.EvaluateModel": handle_evaluate_model,
    f"{NAMESPACE}.CompareToBestModel": handle_compare_to_best,
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


def register_evaluation_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
