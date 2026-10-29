"""Pydantic response models for the Visualization Center.
We avoid pandas types by using standard ``datetime`` objects. This keeps the
schema generation error‑free while the internal pipeline may still use
``pandas.Timestamp``.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):
    anomaly_score: list[float] = Field(..., description="Raw anomaly scores (0‑1)")
    is_anomaly: list[bool] = Field(..., description="Boolean prediction")
    timestamp: list[datetime | None] = Field(
        ..., description="Original timestamps (UTC), may be None"
    )
    host: list[str | None] = Field(..., description="Host identifier")
    service: list[str | None] = Field(..., description="Service identifier")
    template: list[str | None] = Field(..., description="Log‑template after normalization")
    ground_truth: list[bool] | None = Field(
        None, description="Ground‑truth label if supplied"
    )

class RocCurve(BaseModel):
    fpr: list[float]
    tpr: list[float]
    auc: float

class PrCurve(BaseModel):
    precision: list[float]
    recall: list[float]
    average_precision: float

class ConfusionMatrix(BaseModel):
    tn: int
    fp: int
    fn: int
    tp: int

class MetricsResponse(BaseModel):
    roc: RocCurve | None = None
    pr: PrCurve | None = None
    confusion: ConfusionMatrix | None = None
    reduction_ratio: float | None = None
    fallback_message: str | None = None   # set when ground‑truth is missing

class TimelineBucket(BaseModel):
    start: datetime
    end: datetime
    normal: int
    anomaly: int
    no_timestamp: int = 0

class TimelineResponse(BaseModel):
    interval: str
    buckets: list[TimelineBucket]

class GroupingEffectResponse(BaseModel):
    alert_count: int
    incident_count: int
    reduction_percent: float | None = None
    note: str | None = None
