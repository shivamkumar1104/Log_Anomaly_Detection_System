# AIOps Log Anomaly Detection and Alert Grouping Platform

An explainable platform for analyzing application and system logs, identifying unusual
behavior, grouping related alerts, and inspecting the supporting log evidence. An anomaly
is a signal for investigation, not proof of an incident, attack, or root cause.

## Project status

**Phase 1 — project foundation.** This phase establishes the package layout, environment
configuration, architecture documentation, and a Streamlit landing page. The ingestion
pipeline, detector, alert grouping, and API are not implemented yet; they will be added and
tested in subsequent phases.

The existing `loghub/` checkout is left untouched. Dataset provenance, licensing, schema,
and label suitability will be reviewed during Phase 2 before using it for evaluation.

## Architecture

Batch logs will flow through validation and normalization, preprocessing and sensitive-data
handling, template extraction, TF-IDF features, anomaly detection, transparent severity
rules, and alert grouping. The UI, API, and persistence layers will consume shared
application services rather than duplicating detection logic. See
[`docs/architecture.md`](docs/architecture.md) for the module boundaries and workflow.

## Windows setup (PowerShell)

The repository currently has a `.venv` created with Python 3.14. To recreate it:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Development checks

```powershell
python -m ruff check .
python -m pytest
```

## Run the application

From the repository root, with the virtual environment active:

```powershell
streamlit run app.py
```

Or, without activating the environment:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The current page reports project status only; it does not yet accept or analyze logs.

## Planned implementation

1. **Phase 1 — foundation:** package structure, configuration conventions, and architecture.
2. **Phase 2 — data governance:** inspect dataset schema, provenance, labels, and splits.
3. **Phases 3–4 — batch inputs:** validate CSV/text logs, define the event schema, and
   preprocess messages safely.
4. **Phases 5–7 — detection:** extract templates and TF-IDF features, add Isolation Forest
   and a transparent baseline, then assess severity and group related alerts.
5. **Phases 8–9 — investigation and evaluation:** build the dashboard, exports, and
   reproducible metrics using valid labels.
6. **Phases 10–16 — persistence and extensions:** add SQLite and API support, then
   security, live ingestion, and only evaluation-justified advanced features.
7. **Phases 17–20 — quality and operations:** expand automated tests, add Docker and CI,
   document deployment, and report only measured results.

Testing, security, and documentation will be addressed alongside each feature, not deferred
until the final phase.
# Log_Anomaly_Detection_System
