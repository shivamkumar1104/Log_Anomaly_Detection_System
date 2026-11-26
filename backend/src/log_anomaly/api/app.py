"""FastAPI endpoints for log upload, analysis, history, and alert exports."""

from __future__ import annotations

import json
import logging
import os
from io import StringIO
from threading import Lock
from typing import Annotated, Any, Literal
from uuid import uuid4

import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from log_anomaly.api.auth import require_api_key
from log_anomaly.api.visualization import router as visualization_router
from log_anomaly.ingestion.parser import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    IngestionError,
    parse_log_file,
)
from log_anomaly.persistence.sqlite_store import SQLiteStore
from log_anomaly.reports.export import build_analysis_export
from log_anomaly.service import analyze_batch

DATABASE_PATH = os.getenv("LOG_ANOMALY_DATABASE_PATH", "data/log_anomaly.db")
store = SQLiteStore(DATABASE_PATH)
logger = logging.getLogger(__name__)
_upload_jobs: dict[str, dict[str, Any]] = {}
_upload_jobs_lock = Lock()

app = FastAPI(
    title="Anomaly Detect API",
    description="Local-development API for uploading and analyzing log files.",
    version="0.2.0",
)
raw_origins = os.getenv("LOG_ANOMALY_FRONTEND_ORIGIN", "http://localhost:3000")
configured_origins = []
for origin in raw_origins.split(","):
    origin = origin.strip()
    if not origin:
        continue
    if "://" not in origin:
        origin = f"https://{origin}"
    configured_origins.append(origin)
allowed_origins = list(
    set(
        configured_origins
        + [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    visualization_router,
    prefix="/api",
    dependencies=[Depends(require_api_key)],
)


class AnalysisRequest(BaseModel):
    """Validated request body for batch event analysis."""

    events: list[dict[str, Any]] = Field(min_length=1, max_length=10_000)
    method: Literal["auto", "isolation_forest", "baseline", "clustering"] = "auto"
    contamination: float = Field(default=0.1, ge=0.01, le=0.5)
    grouping_window_minutes: int = Field(default=5, ge=1, le=1440)


def _serialize_events(events: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(events.to_json(orient="records", date_format="iso"))


def _analyze(
    events: pd.DataFrame,
    method: str,
    contamination: float,
    grouping_window_minutes: int,
) -> pd.DataFrame:
    try:
        return analyze_batch(
            events,
            method=method,
            contamination=contamination,
            grouping_window_minutes=grouping_window_minutes,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _update_upload_job(job_id: str, **updates: Any) -> None:
    with _upload_jobs_lock:
        job = _upload_jobs.get(job_id)
        if job is not None:
            job.update(updates)


def _process_upload_job(
    job_id: str,
    filename: str,
    content: bytes,
    method: str,
    contamination: float,
    grouping_window_minutes: int,
) -> None:
    _update_upload_job(job_id, status="processing", stage="Parsing log file")
    try:
        events, file_format, confidence, source_encoding = parse_log_file(filename, content)
        _update_upload_job(job_id, stage="Analyzing log events")
        results = _analyze(events, method, contamination, grouping_window_minutes)
        selected_method = str(results["detection_method"].iloc[0])

        _update_upload_job(job_id, stage="Saving analysis")
        analysis_id = store.save_analysis(
            results,
            filename=filename,
            file_format=file_format,
            source_encoding=source_encoding,
            method=selected_method,
        )
    except IngestionError as exc:
        _update_upload_job(job_id, status="failed", stage="Upload failed", detail=str(exc))
        return
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Analysis failed."
        _update_upload_job(job_id, status="failed", stage="Analysis failed", detail=detail)
        return
    except (OSError, ValueError):
        logger.exception("Could not save upload job %s", job_id)
        _update_upload_job(
            job_id,
            status="failed",
            stage="Saving failed",
            detail="Could not save analysis results.",
        )
        return
    except Exception:
        logger.exception("Unexpected error while processing upload job %s", job_id)
        _update_upload_job(
            job_id,
            status="failed",
            stage="Analysis failed",
            detail="An unexpected error occurred while analyzing this file.",
        )
        return

    _update_upload_job(
        job_id,
        status="completed",
        stage="Analysis complete",
        analysis_id=analysis_id,
        file_format=file_format,
        format_confidence=confidence,
        source_encoding=source_encoding,
        method=selected_method,
        configured_anomaly_rate=contamination,
        grouping_window_minutes=grouping_window_minutes,
    )


@app.get("/")
def root() -> dict[str, Any]:
    """Root endpoint to guide users and confirm backend status."""
    return {
        "status": "online",
        "service": "Anomaly Detect API",
        "docs": "/docs",
        "frontend": "http://localhost:3000",
        "message": (
            "Backend is running. Open http://localhost:3000 in your browser "
            "to access the frontend dashboard."
        ),
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return 204 No Content for browser favicon requests."""
    return Response(status_code=204)


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str | int]:
    """Report API process health."""
    return {"status": "ok", "max_upload_mb": MAX_UPLOAD_MB}


@app.post("/api/upload", status_code=202, dependencies=[Depends(require_api_key)])
async def upload_and_analyze(
    file: Annotated[UploadFile, File()],
    background_tasks: BackgroundTasks,
    method: Literal["auto", "isolation_forest", "baseline", "clustering"] = Form("auto"),
    contamination: float = Form(0.1, ge=0.01, le=0.5),
    grouping_window_minutes: int = Form(5, ge=1, le=1440),
) -> dict[str, str]:
    """Accept an upload and process it in the background."""
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in {"csv", "txt", "log", "pdf"}:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a .csv, .txt, .log, or .pdf file.",
        )
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the size limit.")

    content = bytearray()
    while True:
        remaining = MAX_UPLOAD_BYTES + 1 - len(content)
        if remaining <= 0:
            break
        chunk = await file.read(min(1024 * 1024, remaining))
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            break
    await file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the size limit.")

    job_id = str(uuid4())
    with _upload_jobs_lock:
        _upload_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "stage": "Queued for analysis",
        }
    background_tasks.add_task(
        _process_upload_job,
        job_id,
        filename,
        bytes(content),
        method,
        contamination,
        grouping_window_minutes,
    )
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/uploads/{job_id}", dependencies=[Depends(require_api_key)])
def get_upload_status(job_id: str) -> dict[str, Any]:
    """Return the processing stage and result identifier for an upload job."""
    with _upload_jobs_lock:
        job = _upload_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Upload job not found.")
        return dict(job)


@app.post("/api/analyze", dependencies=[Depends(require_api_key)])
@app.post("/api/v1/analyze", dependencies=[Depends(require_api_key)])
def analyze(request: AnalysisRequest) -> dict[str, Any]:
    """Analyze normalized event records with the same workflow used for file uploads."""
    results = _analyze(
        pd.DataFrame(request.events),
        request.method,
        request.contamination,
        request.grouping_window_minutes,
    )
    return {"events": _serialize_events(results)}


@app.get("/api/analyses", dependencies=[Depends(require_api_key)])
def list_analyses(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    """List recent persisted analysis summaries."""
    return {"analyses": store.list_analyses(limit=limit)}


@app.get("/api/analyses/{analysis_id}", dependencies=[Depends(require_api_key)])
def get_analysis(analysis_id: str) -> dict[str, Any]:
    """Get one persisted analysis and its result events."""
    analysis = store.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


@app.get(
    "/api/analyses/{analysis_id}/export",
    dependencies=[Depends(require_api_key)],
)
def export_analysis(
    analysis_id: str,
    format: Literal["pdf", "xlsx"] = Query(...),
    exclude_anomalies: bool = Query(default=True),
) -> Response:
    """Download a structured PDF report or Excel workbook for one analysis."""
    analysis = store.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    content, media_type, extension = build_analysis_export(
        analysis, format=format, exclude_anomalies=exclude_anomalies
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="anomaly-detect-{analysis_id}.{extension}"'
            )
        },
    )


@app.get("/api/alerts", dependencies=[Depends(require_api_key)])
def list_alerts(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    """List anomalous events from recently persisted analyses."""
    return {"alerts": store.list_alerts(limit=limit)}


@app.get("/api/alerts/export", dependencies=[Depends(require_api_key)])
def export_alerts(format: Literal["csv", "json"] = Query(default="csv")) -> Response:
    """Export alert evidence from saved analyses as CSV or JSON."""
    alerts = store.list_alerts()
    if format == "json":
        return Response(
            content=json.dumps(alerts, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="alerts.json"'},
        )
    csv_content = pd.DataFrame(alerts).to_csv(index=False) if alerts else "analysis_id\n"
    return Response(
        content=StringIO(csv_content).getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="alerts.csv"'},
    )

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("log_anomaly.api.app:app", host="0.0.0.0", port=port, reload=False)
