"""Optional SQLite storage for analyzed event batches."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd


class SQLiteStore:
    """Persist sanitized analysis results to a local SQLite database."""

    def __init__(self, path: str | Path = "data/log_anomaly.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_events (
                    event_id TEXT PRIMARY KEY,
                    group_id TEXT,
                    timestamp TEXT,
                    severity TEXT,
                    host TEXT,
                    service TEXT,
                    message TEXT NOT NULL,
                    template TEXT NOT NULL,
                    anomaly_score REAL NOT NULL,
                    is_anomaly INTEGER NOT NULL,
                    explanation TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_format TEXT NOT NULL,
                    source_encoding TEXT NOT NULL,
                    method TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    events_json TEXT NOT NULL
                )
                """
            )

    def save(self, events: pd.DataFrame) -> int:
        """Insert or replace a batch of sanitized events; return the number saved."""
        columns = (
            "event_id",
            "group_id",
            "timestamp",
            "severity",
            "host",
            "service",
            "message",
            "template",
            "anomaly_score",
            "is_anomaly",
            "explanation",
        )
        values = [
            tuple(
                _sqlite_value(record.get(column))
                for column in columns
            )
            for record in events.to_dict(orient="records")
        ]
        with self._connect() as connection:
            connection.executemany(
                "INSERT OR REPLACE INTO analysis_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                values,
            )
        return len(values)

    def save_analysis(
        self,
        events: pd.DataFrame,
        *,
        filename: str,
        file_format: str,
        source_encoding: str,
        method: str,
    ) -> str:
        """Persist a result batch and its metadata; return its stable analysis identifier."""
        self.save(events)
        analysis_id = str(uuid4())
        payload = events.to_json(orient="records", date_format="iso")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analyses
                    (analysis_id, created_at, filename, file_format, source_encoding,
                     method, event_count, events_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    datetime.now(UTC).isoformat(),
                    filename,
                    file_format,
                    source_encoding,
                    method,
                    len(events),
                    payload,
                ),
            )
        return analysis_id

    def list_analyses(self, limit: int = 100) -> list[dict[str, object]]:
        """Return recent analysis summaries without log contents."""
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT analysis_id, created_at, filename, file_format, source_encoding,
                       method, event_count
                FROM analyses ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_analysis(self, analysis_id: str) -> dict[str, object] | None:
        """Return one full stored analysis, or None when it does not exist."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT analysis_id, created_at, filename, file_format, source_encoding,
                       method, event_count, events_json
                FROM analyses WHERE analysis_id = ?
                """,
                (analysis_id,),
            ).fetchone()
        if row is None:
            return None
        columns = (
            "analysis_id", "created_at", "filename", "file_format",
            "source_encoding", "method", "event_count", "events_json",
        )
        record = dict(zip(columns, row, strict=True))
        record["events"] = json.loads(record.pop("events_json"))
        return record

    def list_alerts(self, limit: int = 500) -> list[dict[str, object]]:
        """Return anomalous event rows from recent saved analyses."""
        analyses = self.list_analyses(limit=limit)
        alerts: list[dict[str, object]] = []
        for analysis in analyses:
            stored = self.get_analysis(str(analysis["analysis_id"]))
            if stored is None:
                continue
            for event in stored["events"]:
                if event.get("is_anomaly"):
                    alerts.append({"analysis_id": stored["analysis_id"], **event})
        return alerts[:limit]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _sqlite_value(value: object) -> object:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return int(value)
    return value
