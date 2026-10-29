# backend/src/log_anomaly/api/visualization.py
from __future__ import annotations

import os
from datetime import UTC, datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from log_anomaly.persistence.sqlite_store import SQLiteStore
from log_anomaly.visualization.helpers import process_dataframe
from log_anomaly.visualization.metrics import (
    compute_confusion,
    compute_pr,
    compute_roc,
    reduction_ratio,
)
from log_anomaly.visualization.schemas import (
    GroupingEffectResponse,
    MetricsResponse,
    PredictionResponse,
    TimelineResponse,
)
from log_anomaly.visualization.simulation import generate_synthetic

router = APIRouter(prefix="/visualization", tags=["visualization"])

def _load_last_analysis() -> pd.DataFrame:
    """Load the most recent analysis saved by the upload endpoint."""
    store = SQLiteStore(os.getenv("LOG_ANOMALY_DATABASE_PATH", "data/log_anomaly.db"))
    # The SQLiteStore stores analyses as JSON rows; we reuse its helper to fetch the
    # most recent one and turn it back into a DataFrame.
    recent = store.list_analyses(limit=1)
    if not recent:
        raise HTTPException(status_code=404, detail="No analysis available yet.")
    analysis_id = recent[0]["analysis_id"]
    analysis = store.get_analysis(analysis_id)
    # The stored dict contains a list of event dicts under "events".
    if analysis is None:
        raise HTTPException(status_code=404, detail="No analysis available yet.")
    events = pd.DataFrame(analysis.get("events", []))
    return events

@router.get("/predictions", response_model=PredictionResponse)
def get_predictions():
    df = _load_last_analysis()
    return PredictionResponse(
        anomaly_score=df["anomaly_score"].tolist(),
        is_anomaly=df["is_anomaly"].tolist(),
        timestamp=df["timestamp"].apply(
            lambda value: (
                pd.to_datetime(value, utc=True).to_pydatetime() if value else None
            )
        ).tolist(),
        host=df.get("host").tolist() if "host" in df else [None] * len(df),
        service=df.get("service").tolist() if "service" in df else [None] * len(df),
        template=df.get("template").tolist() if "template" in df else [None] * len(df),
        ground_truth=df.get("ground_truth").tolist() if "ground_truth" in df else None,
    )

@router.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    df = _load_last_analysis()
    if "ground_truth" not in df.columns:
        return MetricsResponse(
            fallback_message="Ground‑truth labels not supplied – metrics unavailable."
        )
    roc = compute_roc(df)
    pr = compute_pr(df)
    conf = compute_confusion(df)
    # reduction ratio based on grouping info already present in the stored analysis
    alert_cnt = int(df["is_anomaly"].sum())
    incident_cnt = int(df.get("group_id").nunique()) if "group_id" in df else 0
    red = reduction_ratio(alert_cnt, incident_cnt)
    return MetricsResponse(
        roc=roc,
        pr=pr,
        confusion=conf,
        reduction_ratio=red,
    )

@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(interval: str = Query("5m", pattern=r"^(\d+)(m|h)$")):
    df = _load_last_analysis()
    # Ensure timestamps are proper pandas datetime (UTC)
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    # Determine bucket size
    size = int(interval[:-1])
    unit = interval[-1]
    if unit == "h":
        freq = f"{size}H"
    else:
        freq = f"{size}T"
    # Build time index
    if df["timestamp_dt"].notna().any():
        start = df["timestamp_dt"].min().floor(freq)
        end = df["timestamp_dt"].max().ceil(freq)
        buckets = pd.date_range(start=start, end=end, freq=freq)
        hist = []
        for i in range(len(buckets) - 1):
            mask = (df["timestamp_dt"] >= buckets[i]) & (df["timestamp_dt"] < buckets[i + 1])
            anomaly_flags = df["is_anomaly"].astype(bool)
            normal = int((~anomaly_flags & mask).sum())
            anomaly = int((anomaly_flags & mask).sum())
            no_ts = int((df["timestamp_dt"].isna() & mask).sum())
            hist.append(
                {
                    "start": buckets[i].to_pydatetime(),
                    "end": buckets[i + 1].to_pydatetime(),
                    "normal": normal,
                    "anomaly": anomaly,
                    "no_timestamp": no_ts,
                }
            )
    else:
        # No timestamps at all – single bucket with counts based on is_anomaly
        hist = [
            {
                "start": datetime.now(UTC),
                "end": datetime.now(UTC),
                "normal": int((~df["is_anomaly"].astype(bool)).sum()),
                "anomaly": int(df["is_anomaly"].astype(bool).sum()),
                "no_timestamp": len(df),
            }
        ]
    return TimelineResponse(interval=interval, buckets=hist)

@router.get("/grouping_effect", response_model=GroupingEffectResponse)
def get_grouping_effect():
    df = _load_last_analysis()
    alert_cnt = int(df["is_anomaly"].sum())
    incident_cnt = int(df.get("group_id").nunique()) if "group_id" in df else 0
    red = reduction_ratio(alert_cnt, incident_cnt)
    note = None
    if red is None:
        note = "No alerts – reduction ratio not applicable."
    return GroupingEffectResponse(
        alert_count=alert_cnt,
        incident_count=incident_cnt,
        reduction_percent=red,
        note=note,
    )

@router.post("/simulation", response_model=PredictionResponse)
def run_simulation(
    size: int = Query(500, ge=1, le=5000),
    prevalence: float = Query(0.05, ge=0.0, le=1.0),
    seed: int | None = None,
):
    df = generate_synthetic(size=size, prevalence=prevalence, seed=seed)
    # Run the same pipeline as real data
    processed = process_dataframe(df)
    # Return the same shape as PredictionResponse for UI consistency
    return PredictionResponse(
        anomaly_score=processed["anomaly_score"].tolist(),
        is_anomaly=processed["is_anomaly"].tolist(),
        timestamp=processed["timestamp"].tolist(),
        host=processed.get("host").tolist() if "host" in processed else [None] * len(processed),
        service=(
            processed.get("service").tolist()
            if "service" in processed
            else [None] * len(processed)
        ),
        template=(
            processed.get("template").tolist()
            if "template" in processed
            else [None] * len(processed)
        ),
        ground_truth=(
            processed.get("ground_truth").tolist()
            if "ground_truth" in processed
            else None
        ),
    )
