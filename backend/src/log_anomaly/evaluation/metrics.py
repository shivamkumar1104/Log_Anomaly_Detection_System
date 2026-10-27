"""Evaluation metrics for predictions aligned to per-event labels."""

from __future__ import annotations

from typing import Any

from sklearn.metrics import precision_recall_fscore_support


def evaluate_predictions(labels: list[bool], predictions: list[bool]) -> dict[str, Any]:
    """Calculate binary precision, recall, and F1 without hiding undefined scores."""
    if len(labels) != len(predictions):
        raise ValueError("Labels and predictions must have the same number of records.")
    if not labels:
        raise ValueError("At least one labeled record is required.")
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0
    )
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "records": len(labels),
    }
