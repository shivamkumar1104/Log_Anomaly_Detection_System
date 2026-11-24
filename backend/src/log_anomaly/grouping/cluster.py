"""Semantic log clustering using TF-IDF and density-based clustering."""

from __future__ import annotations

import re

import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer


def _extract_cluster_meaning(cluster_df: pd.DataFrame) -> str:
    """Extract a concise human-readable description for what a cluster represents."""
    # 1. Dominant service if present
    service = ""
    if "service" in cluster_df.columns:
        services = cluster_df["service"].dropna()
        if not services.empty:
            mode_s = services.mode()
            if not mode_s.empty and str(mode_s.iloc[0]).strip():
                service = str(mode_s.iloc[0]).strip().title()

    # 2. Dominant template or message pattern
    col = "template" if "template" in cluster_df.columns else "message"
    desc = ""
    if col in cluster_df.columns:
        texts = cluster_df[col].dropna()
        if not texts.empty:
            mode_t = texts.mode()
            if not mode_t.empty:
                raw_text = str(mode_t.iloc[0])
                # Clean template tokens like <*>, <NUM>, <IP>, etc.
                cleaned = re.sub(r"<[^>]+>", " ", raw_text)
                # Clean punctuation
                cleaned = re.sub(r"[^\w\s/=-]", " ", cleaned)
                # Filter out pure numbers or single chars
                words = [w for w in cleaned.split() if len(w) > 1 and not w.isdigit()]
                desc = " ".join(words[:4]).strip().title()

    if service and desc:
        return f"{service} - {desc}"
    if desc:
        return desc
    if service:
        return service
    return "Log Pattern"


def cluster_log_events(
    events: pd.DataFrame,
    eps: float = 0.45,
    min_samples: int = 2,
) -> pd.DataFrame:
    """Assign cluster_id to log events based on semantic template similarity.

    Dense clusters represent normal/frequent patterns (Cluster 1: User Login, ...).
    Outliers and isolated/rare templates that do not fit into any dense cluster
    are assigned 'Outlier (Rare/Anomalous)'.
    """
    result = events.copy()
    if result.empty:
        result["cluster_id"] = []
        return result

    messages = (
        result["template"].fillna("").replace("", "<EMPTY>").astype(str).tolist()
        if "template" in result.columns
        else result["message"].fillna("").replace("", "<EMPTY>").astype(str).tolist()
    )

    if len(result) < 2 or len(set(messages)) < 2:
        meaning = _extract_cluster_meaning(result)
        result["cluster_id"] = f"Cluster 1: {meaning}"
        return result

    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
    try:
        matrix = vectorizer.fit_transform(messages)
    except ValueError:
        meaning = _extract_cluster_meaning(result)
        result["cluster_id"] = f"Cluster 1: {meaning}"
        return result

    if matrix.shape[1] == 0:
        meaning = _extract_cluster_meaning(result)
        result["cluster_id"] = f"Cluster 1: {meaning}"
        return result

    # DBSCAN with cosine distance
    clusterer = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    raw_labels = clusterer.fit_predict(matrix)

    # Order clusters by size: largest cluster = Cluster 1, next = Cluster 2, etc.
    valid_labels = [label for label in raw_labels if label != -1]
    label_counts = pd.Series(valid_labels).value_counts().to_dict()

    label_mapping = {}
    for rank, (label, _) in enumerate(
        sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))
    ):
        sub_df = result.iloc[[i for i, lbl in enumerate(raw_labels) if lbl == label]]
        meaning = _extract_cluster_meaning(sub_df)
        label_mapping[label] = f"Cluster {rank + 1}: {meaning}"

    cluster_ids = []
    for i, label in enumerate(raw_labels):
        if label == -1:
            row_meaning = _extract_cluster_meaning(result.iloc[[i]])
            outlier_label = (
                f"Outlier: {row_meaning}" if row_meaning != "Log Pattern" else "Outlier"
            )
            cluster_ids.append(outlier_label)
        else:
            cluster_ids.append(label_mapping.get(label, f"Cluster {label + 1}"))

    result["cluster_id"] = cluster_ids
    return result
