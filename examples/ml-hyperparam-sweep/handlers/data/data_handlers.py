"""Data preparation handlers — PrepareDataset, SplitDataset."""

from __future__ import annotations

import json
import os
from typing import Any

from handlers.shared.ml_utils import generate_synthetic_dataset, split_dataset

NAMESPACE = "ml.Data"


def handle_prepare_dataset(params: dict[str, Any]) -> dict[str, Any]:
    """Handle PrepareDataset event facet."""
    dataset_name = params.get("dataset_name", "synthetic")
    num_features = int(params.get("num_features", 10))
    num_samples = int(params.get("num_samples", 1000))

    dataset = generate_synthetic_dataset(
        name=dataset_name,
        num_features=num_features,
        num_samples=num_samples,
    )
    # Remove internal field before returning
    dataset.pop("_labels", None)

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {
                "message": f"Prepared dataset '{dataset_name}' with {num_samples} samples",
                "level": "success",
            }
        )

    return {"dataset": dataset}


def handle_split_dataset(params: dict[str, Any]) -> dict[str, Any]:
    """Handle SplitDataset event facet."""
    dataset = params.get("dataset", {})
    if isinstance(dataset, str):
        dataset = json.loads(dataset)

    config = params.get("config", {})
    if isinstance(config, str):
        config = json.loads(config)

    num_samples = int(dataset.get("num_samples", 1000))
    train_ratio = float(config.get("train_ratio", 0.7))
    val_ratio = float(config.get("val_ratio", 0.15))
    seed = int(config.get("random_seed", 42))

    result = split_dataset(
        num_samples=num_samples,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
    )

    step_log = params.get("_step_log")
    if step_log:
        step_log.append(
            {
                "message": f"Split {num_samples} samples: train={result['train_count']}, val={result['val_count']}, test={result['test_count']}",
                "level": "success",
            }
        )

    return result


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.PrepareDataset": handle_prepare_dataset,
    f"{NAMESPACE}.SplitDataset": handle_split_dataset,
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


def register_data_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
