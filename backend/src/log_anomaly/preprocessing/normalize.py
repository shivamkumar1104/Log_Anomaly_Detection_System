"""Normalize log messages and mask common identifiers."""

from __future__ import annotations

import re
from uuid import uuid4

import pandas as pd

_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_UUID = re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", re.I)
_LONG_HEX = re.compile(r"\b(?:0x)?[0-9a-f]{12,}\b", re.I)
_LONG_NUMBER = re.compile(r"(?<!\w)\d{4,}(?!\w)")
_SPACE = re.compile(r"[ \t]+")


def normalize_events(frame: pd.DataFrame) -> pd.DataFrame:
    """Return sanitized event messages and normalized timestamps without dropping rows."""
    result = frame.copy()
    if "event_id" not in result:
        result["event_id"] = [str(uuid4()) for _ in range(len(result))]
    result["message"] = result["message"].fillna("").astype(str).map(
        lambda value: _SPACE.sub(" ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    )
    result["template"] = result["message"].map(extract_template)
    if "timestamp" in result:
        parsed = pd.to_datetime(result["timestamp"], errors="coerce", utc=True)
        result["timestamp"] = parsed.map(
            lambda value: value.isoformat() if not pd.isna(value) else None
        )
    else:
        result["timestamp"] = None
    for field in ("severity", "host", "service", "source"):
        if field not in result:
            result[field] = None
    return result


def extract_template(message: str) -> str:
    """Replace volatile IPs, UUIDs, long hex strings, and numeric IDs with placeholders."""
    template = _IP.sub("<IP>", message)
    template = _UUID.sub("<UUID>", template)
    template = _LONG_HEX.sub("<HEX>", template)
    return _LONG_NUMBER.sub("<NUM>", template)
