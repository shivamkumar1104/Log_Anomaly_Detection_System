# Current Architecture

## Implemented flow

```text
Next.js dashboard
  -> FastAPI upload/analyze endpoints
  -> CSV/text/PDF ingestion
  -> normalization/template extraction
  -> frequency baseline or TF-IDF + Isolation Forest
  -> alert grouping
  -> SQLite history
  -> PDF/XLSX/CSV/JSON exports
```

## Verified implementation

- Next.js 16, React 19 and TypeScript frontend.
- FastAPI and reusable Python package modules.
- CSV, text, Apache-shaped text, Java-style text and text-based PDF parsing.
- Per-upload TF-IDF/Isolation Forest, frequency baseline and DBSCAN support.
- Host/service/template/time-window alert grouping.
- Local SQLite analysis and event storage.
- Backend unit/integration tests, frontend lint/build and real BGL upload smoke test.

## Key boundaries

- The API is unauthenticated and must remain local/private.
- Detection is fitted per uploaded file; the notebook artifact is not used by the API.
- Source timestamps and labels are format-dependent.
- SQLite storage is CWD-dependent and lacks migrations, retention and tenant isolation.
- The dashboard is an MVP; charts, server-side search and alert lifecycle are incomplete.

See [PROJECT_AUDIT.md](./PROJECT_AUDIT.md) and [docs/architecture.md](./docs/architecture.md)
for detailed verified findings.
