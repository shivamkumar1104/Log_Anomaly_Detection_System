# backend/src/log_anomaly/visualization/helpers.py
"""Utility functions for the Visualization Center.
- Runs the existing anomaly detection pipeline.
- Selects an adaptive grouping window based on timestamp gaps.
- Returns a pandas DataFrame enriched with grouping meta‑info.
"""
from __future__ import annotations

import pandas as pd
from log_anomaly.detection.analyze import analyze_events
from log_anomaly.grouping.correlate import group_alerts

# Candidate windows (minutes) considered for adaptive grouping.
CANDIDATE_WINDOWS = [1, 2, 5, 10, 15, 30]


def _select_window(df: pd.DataFrame):
    """Select an adaptive grouping window.
    Returns ``(window_minutes, was_fallback, explanation)``.
    """
    if "timestamp" not in df.columns or df["timestamp"].isna().all():
        return 5, True, "Insufficient timestamp data – using default 5 min."
    # Convert to pandas datetime (UTC) – coerce invalid values to NaT.
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dropna().sort_values()
    if ts.empty:
        return 5, True, "No valid timestamps – using default 5 min."
    diffs = ts.diff().dt.total_seconds().dropna() / 60.0  # minutes
    if diffs.empty:
        return 5, True, "Only a single timestamp – using default 5 min."
    median_gap = diffs.median()
    best = min(CANDIDATE_WINDOWS, key=lambda w: abs(w - median_gap))
    return best, False, f"Chosen {best} min based on median inter‑event gap {median_gap:.1f} min."


def process_dataframe(df: pd.DataFrame, method: str = "auto", contamination: float = 0.1) -> pd.DataFrame:
    """Run detection + grouping on a raw DataFrame.
    The function returns a DataFrame that already contains the columns
    required by the API response models.
    """
    # Detection step – returns a DataFrame with anomaly_score, is_anomaly, etc.
    analyzed = analyze_events(df, method=method, contamination=contamination)
    # Adaptive window selection based on timestamps present in ``analyzed``.
    win, fallback, note = _select_window(analyzed)
    # Group alerts using the chosen window.
    grouped = group_alerts(analyzed, window_minutes=win)
    # Store meta‑information for the UI (optional, not persisted).
    grouped.attrs["grouping_window"] = win
    grouped.attrs["grouping_fallback"] = fallback
    grouped.attrs["grouping_note"] = note
    return grouped
