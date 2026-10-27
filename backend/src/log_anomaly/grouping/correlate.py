"""Group anomaly events by host, service, and template within a time window."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd


def group_alerts(frame: pd.DataFrame, window_minutes: int = 5) -> pd.DataFrame:
    """Assign stable group IDs to anomalous records with matching keys and nearby times."""
    if window_minutes < 1:
        raise ValueError("Grouping window must be at least one minute.")
    result = frame.copy()
    result["group_id"] = None
    anomalies = result.index[result["is_anomaly"].astype(bool)].tolist()
    if not anomalies:
        return result

    records: dict[tuple[str, str, str], tuple[pd.Timestamp | None, int]] = {}
    group_number = 0
    def event_time(index: int) -> pd.Timestamp | None:
        timestamp = pd.to_datetime(result.at[index, "timestamp"], errors="coerce", utc=True)
        return None if pd.isna(timestamp) else timestamp

    ordered = sorted(
        anomalies,
        key=lambda index: (
            event_time(index) is None,
            event_time(index) or pd.Timestamp.max.tz_localize("UTC"),
            index,
        ),
    )
    for index in ordered:
        row = result.loc[index]
        key = (str(row.get("host") or ""), str(row.get("service") or ""), str(row["template"]))
        current_time = event_time(index)
        previous = records.get(key)
        group_id = None
        if previous is not None:
            previous_time, previous_group = previous
            if current_time is None and previous_time is None:
                group_id = previous_group
            elif current_time is not None and previous_time is not None:
                if current_time - previous_time <= timedelta(minutes=window_minutes):
                    group_id = previous_group
        if group_id is None:
            group_number += 1
            group_id = group_number
        records[key] = (current_time, group_id)
        result.at[index, "group_id"] = f"INC-{group_id:04d}"
    return result
