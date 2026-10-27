"""Shared application workflow for the dashboard and HTTP API."""

from __future__ import annotations

import pandas as pd

from log_anomaly.detection.analyze import analyze_events
from log_anomaly.grouping.correlate import group_alerts
from log_anomaly.severity.assess import assess_severity


def analyze_batch(
    events: pd.DataFrame,
    method: str = "auto",
    contamination: float = 0.1,
    grouping_window_minutes: int = 5,
) -> pd.DataFrame:
    """Run detection, severity assignment, and alert grouping on one normalized batch."""
    detected = analyze_events(events, method=method, contamination=contamination)
    severity = assess_severity(detected)
    return group_alerts(severity, window_minutes=grouping_window_minutes)
