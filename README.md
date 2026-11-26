# Anomaly Detect

An explainable platform for analyzing application and system logs, identifying unusual
behavior, grouping related alerts, and inspecting the supporting log evidence. An anomaly
is a signal for investigation, not proof of an incident, attack, or root cause.

The project is organized into two main applications: `backend/` contains the Python API
and analysis pipeline, and `frontend/` contains the Next.js dashboard.

## Project status

**Local MVP aligned to the provided architecture.** It accepts CSV and encoded text logs,
parses Apache and Java-style entries (including Java stack traces), normalizes templates,
automatically selects a frequency baseline for small/low-variety inputs or TF-IDF with
Isolation Forest for larger/diverse inputs, assigns rule-based severity, groups alerts,
and provides a Next.js dashboard connected to FastAPI. It can filter detected anomalies
from exports and generate structured PDF and Excel reports. This local setup is not
production-hardened.

No external AI service or API key is used. Analysis runs locally in the Python backend.
The expected anomaly rate is a scoring target, not a guarantee of how many records will be
flagged; tied scores can change the final count. The grouping window controls how close in
time matching alerts must be to join a group.

The existing `loghub/` checkout is left untouched. Dataset provenance, licensing, schema,
and label suitability will be reviewed during Phase 2 before using it for evaluation.

## Architecture

Batch logs will flow through validation and normalization, preprocessing and sensitive-data
handling, template extraction, TF-IDF features, anomaly detection, transparent severity
rules, and alert grouping. The UI, API, and persistence layers will consume shared
application services rather than duplicating detection logic. See
[`docs/architecture.md`](docs/architecture.md) for the module boundaries and workflow.

## Skills and technologies used

This project uses the following practical development and engineering skills:

- **Python backend development:** modular Python package design, type-safe application
  services, configuration management, and reusable domain modules.
- **FastAPI and REST API development:** validated file uploads, analysis, history, alerts,
  exports, health checks, and interactive OpenAPI documentation.
- **Log ingestion and preprocessing:** CSV/text/PDF parsing, encoding detection and
  normalization, Java stack-trace merging, message cleanup, template extraction, and
  sensitive-data masking.
- **Machine learning for anomaly detection:** TF-IDF feature engineering, Isolation Forest,
  frequency-based baselines, configurable anomaly scoring, and per-event evaluation using
  precision, recall, and F1.
- **Explainable detection:** rule-based severity assignment, score thresholds, evidence
  preservation, and host/service/template/time-window alert grouping.
- **Data and persistence engineering:** pandas/NumPy-based processing, local SQLite
  storage, and structured CSV/JSON exports.
- **Report generation:** PDF reports with ReportLab, Excel reports with openpyxl, and
  text extraction from PDFs with pypdf.
- **Frontend development:** Next.js, React, TypeScript, responsive dashboard design,
  Tailwind CSS, and Recharts-based data visualization.
- **Quality and maintainability:** unit and integration testing with pytest, linting with
  Ruff and ESLint, production builds, environment-based configuration, and local-first
  security practices for sensitive log data.

**Note:** Streamlit is not part of the current application runtime. The dashboard is
implemented with Next.js and communicates with the FastAPI backend.

## Windows setup (PowerShell)

Create a Python virtual environment at the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
Push-Location backend
python -m pip install -r requirements-dev.txt
Pop-Location
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.local.example frontend\.env.local
```

If PowerShell blocks activation, use the environment's interpreter directly:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Pop-Location
```

## Development checks

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m pytest
Pop-Location
npm --prefix frontend run lint
npm --prefix frontend run build
```

## Run the application (Next.js + FastAPI)

In **Terminal 1**, start the API from the `backend` folder:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn log_anomaly.api.app:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

In **Terminal 2**, configure and start the frontend:

```powershell
Copy-Item frontend\.env.local.example frontend\.env.local
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open [http://localhost:3000](http://localhost:3000). Upload `.csv`, `.txt`, `.log`, or
text-based `.pdf` files (25 MB maximum). CSV/TXT/LOG encodings are normalized to UTF-8;
PDF text is extracted with pypdf. Scanned PDFs require OCR and are rejected with a clear
error. PDFs must contain recognizable log records; research papers and generic documents
are not valid log datasets. Analysis results and history are saved to local SQLite.

The API is unauthenticated and intended for local development only. Do not expose it to an
untrusted network. Authentication/authorization, rate limiting, Docker, CI/CD, monitoring,
backups, and PostgreSQL are follow-up operational work. SQLite stores raw messages and must
be treated as sensitive log data.

### API endpoints

- `GET /api/health`
- `POST /api/upload` — accepts a multipart upload and starts background analysis (`202 Accepted`)
- `GET /api/uploads/{job_id}` — poll upload-processing status and retrieve the completed analysis ID
- `POST /api/analyze` — analyze normalized event JSON
- `GET /api/analyses` and `GET /api/analyses/{id}`
- `GET /api/analyses/{id}/export?format=pdf|xlsx&exclude_anomalies=true`
- `GET /api/alerts` and `GET /api/alerts/export?format=csv|json`
- `GET /docs` — interactive local API documentation

The website shows separate upload and analysis stages, then opens the saved result
when processing completes. Large evidence tables are paginated so the browser
does not render every log row at once.

### Final checks

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m pytest
Pop-Location
npm --prefix frontend run lint
npm --prefix frontend run build
```

## Folder guide

```text
backend/
  src/log_anomaly/   FastAPI API and reusable analysis modules
  src/log_anomaly/reports/ PDF and Excel report generation
  tests/             Python unit and integration tests
  config/            Backend rules and settings
  data/              Local input and generated database files
  models/            Generated model artifacts
  .env.example       Backend environment-variable template
  pyproject.toml     Python package, test, and lint configuration
  requirements*.txt  Python runtime and development dependencies
frontend/
  src/app/           Next.js pages, layout, and global styles
  src/components/    Dashboard and reusable UI components
  .env.local.example Frontend environment-variable template
docs/                Architecture and project documentation
deployment/          Deployment assets
loghub/              Existing dataset checkout; kept separate from app code
```

## Planned implementation

1. **Completed local foundation:** modular Python package, validated ingestion, encoding
   normalization, PDF extraction, anomaly detection, severity, grouping, and evaluation.
2. **Completed local interface/API MVP:** Next.js dashboard, FastAPI upload/analyze/history
   endpoints, SQLite persistence, and CSV/JSON alert exports.
3. **Remaining:** validate the supplied LogHub checkout's provenance and labels before
   benchmark evaluation; expand security/authentication, API rate limiting, operational
   monitoring, backup policy, Docker, CI/CD, and production deployment.

Testing, security, and documentation will be addressed alongside each feature, not deferred
until the final phase.
# Log_Anomaly_Detection_System
