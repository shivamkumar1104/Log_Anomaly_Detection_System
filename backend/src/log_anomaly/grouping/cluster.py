"""Semantic log clustering using TF-IDF and density-based clustering."""

from __future__ import annotations

import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer


def cluster_log_events(
    events: pd.DataFrame,
    eps: float = 0.45,
    min_samples: int = 2,
) -> pd.DataFrame:
    """Assign cluster_id to log events based on semantic template similarity.

    Dense clusters represent normal/frequent patterns (Cluster 1, Cluster 2...).
    Outliers and isolated/rare templates that do not fit into any dense cluster
    are assigned 'Outlier'.
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
        result["cluster_id"] = "Cluster 1"
        return result

    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
    try:
        matrix = vectorizer.fit_transform(messages)
    except ValueError:
        result["cluster_id"] = "Cluster 1"
        return result

    if matrix.shape[1] == 0:
        result["cluster_id"] = "Cluster 1"
        return result

    # DBSCAN with cosine distance
    clusterer = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
    raw_labels = clusterer.fit_predict(matrix)

    # Order clusters by size: largest cluster = Cluster 1, next = Cluster 2, etc.
    valid_labels = [label for label in raw_labels if label != -1]
    label_counts = pd.Series(valid_labels).value_counts().to_dict()
    label_mapping = {
        label: f"Cluster {rank + 1}"
        for rank, (label, _) in enumerate(
            sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))
        )
    }

    cluster_ids = []
    for label in raw_labels:
        if label == -1:
            cluster_ids.append("Outlier")
        else:
            cluster_ids.append(label_mapping.get(label, f"Cluster {label + 1}"))

    result["cluster_id"] = cluster_ids
    return result
