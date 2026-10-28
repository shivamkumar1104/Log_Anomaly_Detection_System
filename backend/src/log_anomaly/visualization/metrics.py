from __future__ import annotations
import pandas as pd
import numpy as np
from sklearn.metrics import (
    roc_curve, auc,
    precision_recall_curve, average_precision_score,
    confusion_matrix,
)

def _needs_ground_truth(df: pd.DataFrame) -> bool:
    return "ground_truth" not in df.columns

def compute_roc(df: pd.DataFrame):
    if _needs_ground_truth(df):
        return None
    fpr, tpr, _ = roc_curve(df["ground_truth"], df["anomaly_score"])
    return {"fpr": fpr.tolist(), "tpr": tpr.tolist(), "auc": float(auc(fpr, tpr))}

def compute_pr(df: pd.DataFrame):
    if _needs_ground_truth(df):
        return None
    precision, recall, _ = precision_recall_curve(df["ground_truth"], df["anomaly_score"])
    ap = average_precision_score(df["ground_truth"], df["anomaly_score"])
    return {"precision": precision.tolist(), "recall": recall.tolist(),
            "average_precision": float(ap)}

def compute_confusion(df: pd.DataFrame):
    if _needs_ground_truth(df):
        return None
    tn, fp, fn, tp = confusion_matrix(df["ground_truth"], df["is_anomaly"]).ravel()
    return {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}

def reduction_ratio(alerts: int, incidents: int) -> Optional[float]:
    if alerts == 0:
        return None
    return (alerts - incidents) / alerts * 100.0