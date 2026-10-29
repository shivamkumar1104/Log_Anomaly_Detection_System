"""Application service for the shared log analysis workflow."""

from __future__ import annotations

import pandas as pd

from log_anomaly.detection.analyze import analyze_events
from log_anomaly.grouping.correlate import group_alerts


def analyze_batch(
    events: pd.DataFrame,
    *,
    method: str = "auto",
    contamination: float = 0.1,
    grouping_window_minutes: int = 5,
) -> pd.DataFrame:
    """Analyze a batch of events and assign incident groups to anomalies."""
    analyzed = analyze_events(
        events,
        method=method,
        contamination=contamination,
    )
    return group_alerts(analyzed, window_minutes=grouping_window_minutes)
