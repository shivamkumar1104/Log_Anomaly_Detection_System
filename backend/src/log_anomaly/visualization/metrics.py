from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.metrics import (
    auc,
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_curve,
)


def _needs_ground_truth(df: pd.DataFrame) -> bool:
    return "ground_truth" not in df.columns

def compute_roc(df: pd.DataFrame) -> dict[str, Any] | None:
    if _needs_ground_truth(df):
        return None
    fpr, tpr, _ = roc_curve(df["ground_truth"], df["anomaly_score"])
    return {"fpr": fpr.tolist(), "tpr": tpr.tolist(), "auc": float(auc(fpr, tpr))}

def compute_pr(df: pd.DataFrame) -> dict[str, Any] | None:
    if _needs_ground_truth(df):
        return None
    precision, recall, _ = precision_recall_curve(df["ground_truth"], df["anomaly_score"])
    ap = average_precision_score(df["ground_truth"], df["anomaly_score"])
    return {"precision": precision.tolist(), "recall": recall.tolist(),
            "average_precision": float(ap)}

def compute_confusion(df: pd.DataFrame) -> dict[str, int] | None:
    if _needs_ground_truth(df):
        return None
    matrix = confusion_matrix(
        df["ground_truth"],
        df["is_anomaly"],
        labels=[False, True],
    )
    tn, fp, fn, tp = matrix.ravel()
    return {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}

def reduction_ratio(alerts: int, incidents: int) -> float | None:
    if alerts == 0:
        return None
    return (alerts - incidents) / alerts * 100.0