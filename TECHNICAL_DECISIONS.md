# Technical Decisions

## Existing stack

- **Next.js/React/TypeScript:** Keep for the dashboard; add tests before redesign.
- **FastAPI/Python:** Keep; it already separates ingestion, ML and persistence modules.
- **Scikit-learn/TF-IDF:** Keep as baseline. Deep learning is not justified yet.
- **SQLite:** Keep only for local/small deployments until concurrency, relations and durability
  require a managed database.
- **SQLite or PostgreSQL:** Do not change databases until tenant, backup and concurrency needs
  are measured.
- **Redis/message queue:** Not required by the current synchronous batch MVP.
- **Kafka:** Not justified; preserve a simple interface for future asynchronous ingestion.
- **LLM:** Not part of core anomaly detection. Any investigation assistant requires a separate,
  approved use case.

## Detection contract

The API currently fits on each uploaded file. It should either remain explicitly documented as
per-file novelty scoring or become a versioned, trained-and-serve pipeline. The latter requires
legitimate datasets, source-separated or time-separated holdouts and threshold provenance.

## Evidence rules

- Never fabricate logs or metrics.
- Preserve raw evidence separately from masked templates.
- Label ground truth separately from model predictions.
- Report in-sample metrics only as exploratory, never as production quality.
