# backend/src/log_anomaly/visualization/schemas.py
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
import pandas as pd

class PredictionResponse(BaseModel):
    anomaly_score: List[float] = Field(..., description="Raw anomaly scores (0‑1)")
    is_anomaly: List[bool] = Field(..., description="Boolean prediction")
    timestamp: List[Optional[pd.Timestamp]] = Field(..., description="Original timestamps, may be None")
    host: List[Optional[str]] = Field(..., description="Host identifier")
    service: List[Optional[str]] = Field(..., description="Service identifier")
    template: List[Optional[str]] = Field(..., description="Log‑template after normalization")
    ground_truth: Optional[List[bool]] = Field(None, description="Ground‑truth label if supplied")

class RocCurve(BaseModel):
    fpr: List[float]
    tpr: List[float]
    auc: float

class PrCurve(BaseModel):
    precision: List[float]
    recall: List[float]
    average_precision: float

class ConfusionMatrix(BaseModel):
    tn: int
    fp: int
    fn: int
    tp: int

class MetricsResponse(BaseModel):
    roc: Optional[RocCurve] = None
    pr: Optional[PrCurve] = None
    confusion: Optional[ConfusionMatrix] = None
    reduction_ratio: Optional[float] = None
    fallback_message: Optional[str] = None   # set when ground‑truth is missing

class TimelineBucket(BaseModel):
    start: pd.Timestamp
    end: pd.Timestamp
    normal: int
    anomaly: int
    no_timestamp: int = 0

class TimelineResponse(BaseModel):
    interval: str
    buckets: List[TimelineBucket]

class GroupingEffectResponse(BaseModel):
    alert_count: int
    incident_count: int
    reduction_percent: Optional[float] = None
    note: Optional[str] = None