"""Per-file anomaly scoring with automatic detector selection."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer

from log_anomaly.preprocessing.normalize import normalize_events


def analyze_events(
    events: pd.DataFrame, method: str = "auto", contamination: float = 0.1
) -> pd.DataFrame:
    """Fit features and detectors on one uploaded file, returning scores and explanations."""
    if method not in {"auto", "isolation_forest", "baseline"}:
        raise ValueError("Method must be 'auto', 'isolation_forest', or 'baseline'.")
    if not 0.01 <= contamination <= 0.5:
        raise ValueError("Contamination must be between 0.01 and 0.5.")
    result = normalize_events(events)
    if result.empty:
        raise ValueError("At least one log event is required.")

    messages = result["template"].replace("", "<EMPTY>").tolist()
    counts = result["template"].value_counts()
    frequency_scores = result["template"].map(lambda template: 1.0 / counts[template]).to_numpy()
    baseline = _scale(frequency_scores)

    unique_messages = len(set(messages))
    selected_method = method
    if method == "auto":
        selected_method = (
            "isolation_forest"
            if len(result) >= 20 and unique_messages >= 5
            else "baseline"
        )

    if len(result) < 3 or unique_messages < 2:
        isolation = baseline.copy()
    else:
        matrix = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b").fit_transform(messages)
        if matrix.shape[1] == 0:
            isolation = baseline.copy()
        else:
            model = IsolationForest(
                contamination=contamination, n_estimators=100, random_state=42, n_jobs=1
            )
            model.fit(matrix)
            isolation = _scale(-model.decision_function(matrix))

    scores = isolation if selected_method == "isolation_forest" else baseline
    result["anomaly_score"] = scores
    result["baseline_score"] = baseline
    if np.isclose(float(np.min(scores)), float(np.max(scores))):
        result["is_anomaly"] = False
    else:
        result["is_anomaly"] = scores >= np.quantile(scores, 1 - contamination)
    result["detection_method"] = selected_method
    result["explanation"] = result.apply(
        lambda row: _explanation(row, selected_method, counts), axis=1
    )
    return result


def _scale(values: np.ndarray) -> np.ndarray:
    low, high = float(np.min(values)), float(np.max(values))
    if np.isclose(low, high):
        return np.zeros(len(values), dtype=float)
    return (values - low) / (high - low)


def _explanation(row: pd.Series, method: str, counts: pd.Series) -> str:
    template_frequency = int(counts[row["template"]])
    if method == "baseline":
        return f"Template occurred {template_frequency} time(s) in this file."
    return (
        "Rare message template; Isolation Forest score "
        f"{row['anomaly_score']:.3f}. Template occurred {template_frequency} time(s)."
    )
