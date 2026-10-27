# Backend

Python FastAPI backend and the shared log analysis pipeline.

## Contents

- `src/log_anomaly/api/` — HTTP endpoints and request validation.
- `src/log_anomaly/ingestion/` — upload validation, text encoding, CSV/log/PDF parsing.
- `src/log_anomaly/preprocessing/` — event and message normalization.
- `src/log_anomaly/detection/` — anomaly scoring.
- `src/log_anomaly/severity/` and `src/log_anomaly/grouping/` — severity rules and alert correlation.
- `src/log_anomaly/persistence/` — SQLite analysis history and alert storage.
- `src/log_anomaly/reports/` — structured PDF and Excel exports.
- `tests/` — backend unit and integration tests.
- `config/` — severity rules.
- `data/` — local input data and generated SQLite database.
- `models/` — generated model artifacts.

## Setup and run (Windows PowerShell)

The shared virtual environment is created at the repository root. From the repository root:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Pop-Location
Copy-Item backend\.env.example backend\.env
```

Start the API from this directory:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn log_anomaly.api.app:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

API documentation is available at http://127.0.0.1:8000/docs.

Run backend checks from this directory:

```powershell
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m pytest
```
