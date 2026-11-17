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

## Training notebook

Open [the Colab-compatible training notebook](../notebooks/log_anomaly_training.ipynb) to
compare Isolation Forest, Local Outlier Factor, One-Class SVM, and a rare-template baseline
on structured CSVs or plain-text logs, and shows interactive charts of frequent templates,
flag rates, and anomaly-score distributions. Run all cells in Colab or Jupyter. For measured
accuracy, precision, recall, and F1, supply event-level binary labels; for cross-dataset
generalization, set the dataset-type group column to hold out entire log sources. The included
2,000-event HDFS sample has no ground-truth anomaly labels, so its flagged rates are not
accuracy results. The notebook saves the selected Isolation Forest and its TF-IDF vectorizer
to `backend/models/log_anomaly_isolation_forest.joblib` when run from the repository root.

The API currently fits a detector per uploaded file in
`src/log_anomaly/detection/analyze.py`; it does not load or persist the notebook's trained
artifact.

Local development allows uploads up to 100 MB via `LOG_ANOMALY_MAX_UPLOAD_MB` in `.env`.
The active limit is returned by `/api/health` and shown in the frontend. Render Free stays at
25 MB. File parsing and model fitting are synchronous and memory-intensive, so a larger limit
does not guarantee that a very large or very high-row-count file can be analyzed on a small
machine; split it or use a machine with more available RAM.

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
