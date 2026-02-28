"""Synthetic ML stubs for hyperparameter sweep — pure Python, no external deps."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any


def generate_synthetic_dataset(
    name: str = "synthetic",
    num_features: int = 10,
    num_samples: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a synthetic dataset descriptor."""
    rng = random.Random(seed)
    feature_names = [f"feature_{i}" for i in range(num_features)]
    labels = [rng.randint(0, 1) for _ in range(num_samples)]
    return {
        "name": name,
        "num_features": num_features,
        "num_samples": num_samples,
        "feature_names": feature_names,
        "file_path": f"/data/{name}/features.csv",
        "labels_path": f"/data/{name}/labels.csv",
        "_labels": labels,
    }


def split_dataset(
    num_samples: int,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, Any]:
    """Split a dataset into train/val/test partitions by count."""
    train_count = int(num_samples * train_ratio)
    val_count = int(num_samples * val_ratio)
    test_count = num_samples - train_count - val_count
    return {
        "train_path": "/data/splits/train.csv",
        "val_path": "/data/splits/val.csv",
        "test_path": "/data/splits/test.csv",
        "train_count": train_count,
        "val_count": val_count,
        "test_count": test_count,
    }


def train_model_stub(
    dataset_info: dict[str, Any] | None,
    hyperparams: dict[str, Any],
    model_config: dict[str, Any] | None = None,
    run_label: str = "run",
    seed: int = 42,
) -> dict[str, Any]:
    """Deterministic training stub — metrics derived from hyperparams."""
    lr = float(hyperparams.get("learning_rate", 0.01))
    epochs = int(hyperparams.get("epochs", 50))
    dropout = float(hyperparams.get("dropout", 0.3))
    batch_size = int(hyperparams.get("batch_size", 32))

    # Deterministic loss: lower lr + more epochs + moderate dropout → lower loss
    raw_loss = lr * 10.0 + 1.0 / (epochs + 1) + abs(dropout - 0.25) * 0.5
    h = hashlib.md5(f"{run_label}:{seed}".encode()).hexdigest()
    noise = (int(h[:8], 16) % 1000) / 10000.0  # 0..0.1
    final_loss = max(0.01, raw_loss + noise)

    # Accuracy via sigmoid of inverse loss
    accuracy = 1.0 / (1.0 + math.exp(final_loss * 2.0 - 2.0))
    accuracy = min(0.99, max(0.50, accuracy))

    model_type = "mlp"
    if model_config:
        model_type = model_config.get("model_type", "mlp")

    model_id = f"{model_type}_{run_label}_{seed}"
    training_time_s = int(epochs * batch_size * 0.01 + noise * 100)

    return {
        "model_id": model_id,
        "run_label": run_label,
        "final_loss": round(final_loss, 6),
        "accuracy": round(accuracy, 6),
        "training_time_s": training_time_s,
        "hyperparams": hyperparams,
    }


def evaluate_model_stub(
    model_id: str,
    test_path: str = "/data/splits/test.csv",
    seed: int = 42,
) -> dict[str, Any]:
    """Deterministic evaluation stub — metrics from hash of model_id."""
    h = hashlib.md5(f"{model_id}:{seed}".encode()).hexdigest()
    base = int(h[:8], 16) / 0xFFFFFFFF  # 0..1

    accuracy = 0.60 + base * 0.35  # 0.60..0.95
    precision = 0.55 + base * 0.40  # 0.55..0.95
    recall = 0.50 + base * 0.40  # 0.50..0.90
    f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    tp = int(50 + base * 40)
    fp = int(10 + (1 - base) * 20)
    fn = int(10 + (1 - base) * 20)
    tn = 100 - tp - fp - fn
    confusion_matrix = [[max(0, tp), max(0, fp)], [max(0, fn), max(0, tn)]]

    return {
        "model_id": model_id,
        "accuracy": round(accuracy, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1_score": round(f1, 6),
        "confusion_matrix": confusion_matrix,
    }


def compare_results(
    eval_results: list[dict[str, Any]],
    metric_name: str = "f1_score",
) -> dict[str, Any]:
    """Compare evaluation results by a given metric and return ranking."""
    if not eval_results:
        return {
            "best_model_id": "",
            "metric_name": metric_name,
            "ranking": [],
            "summary": "No results to compare.",
        }

    ranked = sorted(eval_results, key=lambda r: r.get(metric_name, 0), reverse=True)
    ranking = [{"model_id": r.get("model_id", ""), "score": r.get(metric_name, 0)} for r in ranked]
    best = ranked[0]
    return {
        "best_model_id": best.get("model_id", ""),
        "metric_name": metric_name,
        "ranking": ranking,
        "summary": f"Best model: {best.get('model_id', '')} with {metric_name}={best.get(metric_name, 0):.4f}",
    }


def generate_report_text(
    comparison: dict[str, Any],
    dataset_name: str,
    sweep_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate a synthetic sweep report."""
    import datetime

    total_configs = len(comparison.get("ranking", []))
    best_id = comparison.get("best_model_id", "unknown")
    metric = comparison.get("metric_name", "f1_score")
    ranking = comparison.get("ranking", [])
    best_score = ranking[0]["score"] if ranking else 0

    summary_text = (
        f"Hyperparameter sweep on '{dataset_name}': "
        f"evaluated {total_configs} configurations. "
        f"Best model '{best_id}' achieved {metric}={best_score:.4f}. "
        f"Config: {sweep_config}."
    )

    return {
        "dataset_name": dataset_name,
        "total_configs": total_configs,
        "summary_text": summary_text,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "best_config": comparison.get("ranking", [{}])[0] if ranking else {},
    }
