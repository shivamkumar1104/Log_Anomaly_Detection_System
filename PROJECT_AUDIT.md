# Log Anomaly Detection System — Technical Audit

**Audit date:** 2026-11-17  
**Scope:** Current repository source, frontend, backend, tests, notebook and bundled dataset evidence, configuration, documentation, and Render deployment manifest.

## Executive assessment

The repository implements a useful **local batch-analysis MVP**: a Next.js dashboard, FastAPI upload and analysis endpoints, several CSV/text/PDF ingestion paths, per-file anomaly scoring, alert grouping, SQLite history, and exports. It is **not ready for an untrusted public or production deployment**. The most important blockers are unauthenticated access to log-bearing endpoints, unbounded and synchronous file analysis, sensitive message persistence, and the absence of an independently validated ML benchmark.

No measured detector accuracy, false-positive rate, latency, throughput, or memory result is asserted in this report. The bundled 2,000-event HDFS sample has no event labels, and the synthetic visualization endpoint generates random labels. Neither is evidence of model performance.

### Audit limits

- Findings are from source/configuration/documentation inspection. Test source was reviewed, but tests, builds, live endpoints, dependency vulnerability scans, accessibility checks, and load tests were **not run**. Accordingly, the presence of a test is not a claim that it passes.
- No implementation, dependency, or deployment configuration was changed. This report is the only requested audit deliverable.
- “Implemented” below means that a source path exists; it does not certify runtime correctness or production suitability.

## Existing architecture

```text
Browser: Next.js App Router / React / TypeScript
  └── Dashboard: upload, result filters, history, exports
        └── HTTP requests to FastAPI
              ├── file validation, decoding, CSV/text/PDF parsing
              ├── pandas event frame and message-template normalization
              ├── per-file frequency baseline / TF-IDF + Isolation Forest /
              │   DBSCAN clustering
              ├── time/key alert grouping
              ├── SQLite analysis history and event JSON
              └── CSV/JSON/PDF/XLSX exports
```

The upload path is implemented in [app.py](./backend/src/log_anomaly/api/app.py#L116): read the uploaded bytes, parse to events, call the shared service, persist the result, then return all event rows. [analyze_batch](./backend/src/log_anomaly/service.py#L11) calls scoring and grouping. SQLite is the only implemented persistence backend in [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L17). The independent training notebook can save a model artifact, but the API fits per-upload models and does not load that artifact; see [backend/README.md](./backend/README.md#L20).

The app also has a visualization API. Its simulation route uses generated events and generated labels ([visualization.py](./backend/src/log_anomaly/api/visualization.py#L141), [simulation.py](./backend/src/log_anomaly/visualization/simulation.py#L29)); it is not a benchmark. The frontend dashboard does not call these visualization endpoints.

## Feature status

| Area | Status | Verified in source |
|---|---|---|
| Upload/API | **Implemented, partial** | Health, upload, normalized-event analysis, history/detail, alerts, and exports exist. Analysis routes have no authentication. File upload has a byte ceiling, but no parsed-row ceiling. |
| Parsing | **Implemented, partial** | CSV with recognized message columns, common Apache access-log shape, Java-style starts/stack traces, generic text, encodings, and text-based PDF extraction. Parser coverage is narrow; unknown text can fall through to generic parsing. |
| TF-IDF / Isolation Forest | **Implemented, partial** | TF-IDF and Isolation Forest are fit per input; a frequency baseline and DBSCAN clustering are also implemented. Scores are file-relative, not calibrated probabilities. Small forced-IF inputs can be mislabeled as using Isolation Forest when the score is actually the baseline. |
| Evaluation | **Partially implemented; not validated** | The dashboard calculates precision/recall/F1 when every uploaded event has a recognized binary label. These are in-sample comparisons, not held-out generalization results. A separate metrics API expects a different label field. |
| Severity | **Documented, but not wired into the main pipeline** | YAML rules and `assess_severity` exist; the shared service does not call them. Upload results preserve parsed source severity or leave it empty rather than applying the configured score thresholds. |
| Grouping | **Implemented, partial** | Anomalies are grouped by host/service/template and time proximity. Group identity and maximum incident span are not persisted as a separate domain record. |
| SQLite/history | **Implemented for local MVP** | Analyses and event JSON can be saved/listed/read. No migrations, retention, tenant boundary, or durable deployment storage is configured. |
| Dashboard/exports | **Implemented, partial** | Single-page upload/results/history and CSV/JSON/PDF/XLSX export exist. No alert lifecycle, server-side event pagination/search, or rendered charts are present. |
| Automated tests | **Partial; execution unverified** | Three backend test modules cover selected unit/API paths. No frontend test source or application CI test workflow was found. |
| Docker/deployment | **Partial** | Render web-service configuration exists. No Dockerfile/Compose configuration, application CI/CD, monitoring, backup/restore procedure, or rollback evidence was found. |

### What is fully implemented in source (within the narrow MVP scope)

No behavior is marked **runtime-verified** because tests and the application were not run. The following bounded behaviors do have complete source paths: upload extension/byte-limit checks and explicit PDF validation; CSV, common Apache access-log, Java-style, and generic text parsing; per-batch baseline/Isolation Forest scoring for supported inputs; time/key grouping; SQLite save/list/detail; and the implemented export formats. These are not claims of broad format compatibility, reliable ML performance, or production readiness.

### Broken, missing, and partial classifications

- **Broken or misleading paths:** BUG-01 through BUG-06 above (effective detector metadata, severity integration, metric label contract, in-sample evaluation presentation, detector copy/work, and upload-limit mismatch).
- **Partially implemented:** format coverage and raw-record traceability; label normalization/evaluation; SQLite durability/retention; UI investigation workflows; and deployment operations.
- **Missing:** authentication/authorization and tenant isolation; upload rate/concurrency/row controls; secret redaction/retention; event pagination/search; schema migrations and durable storage; application CI/CD and frontend tests; monitoring, backups, restore, rollback, and real benchmark evaluation.
- **Planned in project documentation:** authentication, rate limiting, PostgreSQL, monitoring, backups, Docker, CI, and production hardening. The docs do not indicate that these are complete.

### Planned/documented, not implemented

The README and architecture document explicitly list authentication/authorization, rate limiting, PostgreSQL, monitoring, backups, Docker, CI, and production hardening as follow-up work ([README.md](./README.md#L177), [architecture.md](./docs/architecture.md#L92)). Vendor-wide parser support and Drain3 template mining are also documented as not implemented. A Render manifest is present, but does not make these controls complete.

## Critical findings

### SEC-01 — Public deployment configuration exposes unauthenticated log data

**Severity: Critical — production blocker**

The Render manifest declares the backend as a public web service ([render.yaml](./render.yaml#L1)). The upload, analysis history/detail, alert, and export routes have no authentication or authorization dependency ([app.py](./backend/src/log_anomaly/api/app.py#L116), [app.py](./backend/src/log_anomaly/api/app.py#L179), [app.py](./backend/src/log_anomaly/api/app.py#L218)). Analysis detail returns all stored event content, and exports include log messages ([sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L130), [reports/export.py](./backend/src/log_anomaly/reports/export.py#L75)).

**Impact:** If deployed as configured, an unauthenticated caller can submit expensive analyses and read log data uploaded by other users. Logs can contain credentials, identifiers, customer data, or internal infrastructure details.

**Recommendation:** Keep the service private until identity, authorization, tenant-scoped data access, and security tests exist. Require authentication on every log-bearing endpoint; restrict health checks to minimal status data. Treat current database contents as sensitive.

### SEC-02 — Spreadsheet exports do not neutralize formula-leading log values

**Severity: High**

Untrusted event values are written directly into XLSX cells ([reports/export.py](./backend/src/log_anomaly/reports/export.py#L173), [reports/export.py](./backend/src/log_anomaly/reports/export.py#L178)). The alert CSV uses pandas serialization ([app.py](./backend/src/log_anomaly/api/app.py#L224)); the browser CSV exporter only quotes values ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L67), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L464)). CSV quoting does not prevent spreadsheet applications from treating formula-leading cell content as a formula.

**Impact:** Opening an export containing a malicious log value in a spreadsheet may execute a formula.

**Recommendation:** Centralize safe spreadsheet serialization and neutralize formula-leading text (including leading whitespace/control characters) for every CSV/XLSX export. Keep the unmodified evidence separate in the application’s JSON/history path where access is controlled.

### SEC-03 — Upload work is synchronous and has no file-row bound or rate limit

**Severity: High**

`/api/upload` reads the whole bounded file into memory and then performs parsing, pandas conversion, clustering, scoring, and persistence in the async request handler ([app.py](./backend/src/log_anomaly/api/app.py#L117), [app.py](./backend/src/log_anomaly/api/app.py#L132)). The parser byte limit is configurable from 1 to 1,024 MB ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L17)), but uploaded CSV/text files have no event-count cap. The normalized-event endpoint does have a 10,000-event cap ([app.py](./backend/src/log_anomaly/api/app.py#L54)). DBSCAN clustering is performed for every analyzed batch ([analyze.py](./backend/src/log_anomaly/detection/analyze.py#L32), [cluster.py](./backend/src/log_anomaly/grouping/cluster.py#L12)).

**Impact:** A high-row-count file or concurrent requests can consume substantial CPU and memory and block the API event loop. A file-byte limit alone does not bound parsed rows, token cardinality, or clustering cost.

**Recommendation:** Before exposure, enforce row/token/page limits before expensive work, add rate and concurrency controls, and return explicit overload errors. Consider a bounded job worker only if measured workload requires it. Do not rely on the browser limit as a security control.

### SEC-04 — Original log messages are persisted and exported without redaction or retention

**Severity: High**

Normalization creates a masked template but keeps the original `message` ([normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L23)). SQLite stores both messages and a full JSON copy of events ([sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L53), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L82)). No retention/deletion policy is implemented.

**Impact:** Template masking is not secret/PII redaction. Persistent history and exports may retain sensitive data indefinitely.

**Recommendation:** Define raw-versus-redacted data handling, access control, retention, deletion, and deployment encryption requirements. Make any raw evidence retention deliberate and auditable.

### SEC-05 — CORS allows a broad Render-origin pattern

**Severity: Medium; defense-in-depth**

The API always allows localhost origins and accepts any matching `*.onrender.com` origin with credentials enabled and all methods/headers ([app.py](./backend/src/log_anomaly/api/app.py#L31), [app.py](./backend/src/log_anomaly/api/app.py#L46)). CORS is not authentication and does not stop non-browser clients, but this is broader browser-origin trust than a single configured frontend requires.

**Recommendation:** Allow only exact configured origins in production and disable credentials unless a specific authenticated cookie design needs them. Keep direct API access protected independently.

## Verified functional gaps and bugs

### BUG-01 — Explicit small-input Isolation Forest requests can return baseline scores as Isolation Forest

In `analyze_events`, when there are fewer than three rows or fewer than two templates, the code copies the frequency baseline into `scores` for an explicitly requested `isolation_forest`, but leaves `selected_method` as `"isolation_forest"` ([analyze.py](./backend/src/log_anomaly/detection/analyze.py#L36), [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L59), [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L79)). The response method and explanation can therefore claim Isolation Forest when no Isolation Forest score was used.

**Recommendation:** Report the effective detector separately or make the fallback explicit in the response and explanation.

### BUG-02 — The configured severity rules are not applied by upload or analysis

`assess_severity` reads source severity and score thresholds ([assess.py](./backend/src/log_anomaly/severity/assess.py#L13)); the shared analysis service calls only `analyze_events` and `group_alerts` ([service.py](./backend/src/log_anomaly/service.py#L11)). The YAML file is therefore not on the main request path. This conflicts with README and architecture claims that severity is assigned ([README.md](./README.md#L11), [severity_rules.yaml](./backend/config/severity_rules.yaml)).

**Recommendation:** Either wire a documented derived-severity step into the shared pipeline and distinguish source severity from derived risk, or remove the implementation claim.

### BUG-03 — Parsed labels do not reach the visualization metrics endpoint in its expected field

CSV aliases such as `label`, `ground_truth`, and `target` are mapped to the `label` field ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L49), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L262)). The dashboard understands a limited set of binary label strings and computes P/R/F1 itself ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L63), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L147)). In contrast, `/api/visualization/metrics` checks only for a `ground_truth` column ([visualization.py](./backend/src/log_anomaly/api/visualization.py#L61)). A labeled upload parsed into `label` therefore gets the “labels not supplied” fallback from that endpoint.

The bundled BGL sample uses `-` for non-alert and alert-category strings for alert records ([BGL sample](./loghub/BGL/BGL_2k.log_structured.csv#L1), [BGL README](./loghub/BGL/README.md#L1)); those values are not accepted by the dashboard’s binary mapping. Explicit, dataset-specific label normalization is required before BGL can support dashboard metrics.

### BUG-04 — Dashboard metrics are in-sample, not a held-out evaluation

The request pipeline fits its vectorizer and detector on the full uploaded batch ([analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63), [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L70)). The dashboard then compares those same events’ predictions to their labels ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L147)). These P/R/F1 values describe agreement on the analyzed batch; they do not establish held-out performance or cross-source generalization.

**Recommendation:** Label these values as in-sample descriptive metrics or move performance reporting to a reproducible holdout workflow with a documented split and threshold selection protocol.

### BUG-05 — Detector selection and frontend copy do not match

Automatic selection chooses the baseline for fewer than 20 events or fewer than five distinct templates; otherwise it chooses Isolation Forest ([analyze.py](./backend/src/log_anomaly/detection/analyze.py#L36)). The UI copy says “TF-IDF + Isolation Forest & semantic clustering” and “optimal 10% anomaly threshold” ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L405)), although 10% is a configurable scoring target and auto mode may use the baseline. Furthermore, the baseline branch still fits Isolation Forest for sufficiently varied data before discarding its scores ([analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63), [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L72)). Clustering also performs its own TF-IDF/DBSCAN pass. This adds work and makes the actual algorithm harder to explain.

**Recommendation:** Make detector selection and explanation accurately reflect the effective scoring method; avoid fitting unused detectors while preserving cluster metadata only if the UI needs it.

### BUG-06 — Frontend upload limit and documentation disagree with backend configuration

The frontend hard-codes a 25 MB file limit ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L9), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L182)). The backend defaults to 100 MB locally and permits configuration up to 1,024 MB ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L17)); the Render manifest sets 25 MB ([render.yaml](./render.yaml#L21)). The health endpoint returns the active backend limit, but the dashboard only checks health status and does not read that value ([app.py](./backend/src/log_anomaly/api/app.py#L109), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L102)). The backend README says the active limit is shown in the frontend ([backend/README.md](./backend/README.md#L36)), which the current UI does not do.

**Recommendation:** Display/use the health response limit or align the client/server setting, and correct the README.

## Ingestion and data integrity

### Present behavior

- CSV parsing uses pandas and supports known message aliases; the parser prefers `EventTemplate` to `Content` ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L30), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L242)). This can discard the original content as the primary message; no separate raw-record field or source row locator is retained.
- Text decoding supports BOM-marked UTF variants and charset detection. Binary/NUL/control-heavy content is rejected ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L56), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L100)).
- Apache parsing targets a common access-log prefix, not every Apache log format. Java-style timestamped starts and indented stack-trace continuation exist. Other text falls back to generic line parsing ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L24), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L289)).
- PDF uploads check the signature, encryption, page count, extracted text size, and recognizable log-like records. Scanned PDFs require OCR and are rejected ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L180)).
- Upload accepts `.csv`, `.txt`, `.log`, and `.pdf`; it strips directory components from the supplied filename and enforces a backend byte ceiling ([app.py](./backend/src/log_anomaly/api/app.py#L117)).

### Missing or partial

There is no structured JSON/JSONL, EVTX, vendor parser registry, or general Python/syslog multiline parser. Heuristic format confidence is not a parser-accuracy measurement. A generic text fallback may accept an unsupported layout and turn each line into an event. There is no file-upload row limit or traceability metadata (source hash, line/row/page, parser version). The project documentation itself describes robust vendor support and Drain3 as future work ([architecture.md](./docs/architecture.md#L92)).

The HDFS structured CSV contains `Content` and `EventTemplate` but no label column ([HDFS sample](./loghub/HDFS/HDFS_2k.log_structured.csv#L1)). The notebook’s saved run reports 2,000 events, 14 templates, and no label column; its metrics cell skips evaluation ([training notebook](./notebooks/log_anomaly_training.ipynb#L430), [training notebook](./notebooks/log_anomaly_training.ipynb#L471), [training notebook](./notebooks/log_anomaly_training.ipynb#L3465)). These are dataset facts, not model-performance evidence.

## ML, false positives, and evaluation

- **Features:** TF-IDF is fit per uploaded file over normalized message templates. Normalization masks IPv4-like strings, UUIDs, long hex strings, and long numbers in the template but does not redact the original message ([normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L10)).
- **Isolation Forest:** Fixed `n_estimators=100`, `random_state=42`, and `n_jobs=1`; detector output is min-max scaled within the current file ([analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63)). The result is a relative score, not a probability calibrated across files.
- **Baseline:** Inverse per-file template frequency is scaled and quantile-thresholded. It is a transparent rarity heuristic, not a measure of incident severity or accuracy. Score ties can make the flagged fraction differ from the requested contamination.
- **Clustering:** DBSCAN uses cosine distance on TF-IDF and returns cluster IDs/outliers ([cluster.py](./backend/src/log_anomaly/grouping/cluster.py#L12)). Cluster membership is shown in the UI, but for baseline/Isolation Forest modes it is not the selected detector’s score.
- **False positives:** No analyst feedback, allowlist, cost-sensitive threshold calibration, or feedback loop exists. The configurable contamination is not evidence that the actual false-positive rate equals that value.
- **Evaluation code:** `evaluate_predictions` computes binary precision/recall/F1 ([metrics.py](./backend/src/log_anomaly/evaluation/metrics.py#L10)); visualization code offers ROC/PR/confusion calculations ([visualization/metrics.py](./backend/src/log_anomaly/visualization/metrics.py#L18)). These utilities do not constitute a validated benchmark. The notebook supports a random stratified event split when valid binary labels exist, but that does not establish source- or time-separated generalization ([training notebook](./notebooks/log_anomaly_training.ipynb#L3475)).
- **Synthetic endpoint:** `generate_synthetic` assigns `ground_truth` using an independent random draw ([simulation.py](./backend/src/log_anomaly/visualization/simulation.py#L29), [simulation.py](./backend/src/log_anomaly/visualization/simulation.py#L54)). It must not be used to claim model performance.
- **No verified result:** No real labeled holdout benchmark or measured performance was run for this audit.

## API, database, error handling, and performance

### API behavior

Implemented routes include health, `/api/upload`, `/api/analyze` and `/api/v1/analyze`, analysis list/detail, PDF/XLSX analysis export, and alert list/CSV/JSON export ([app.py](./backend/src/log_anomaly/api/app.py#L109), [app.py](./backend/src/log_anomaly/api/app.py#L116), [app.py](./backend/src/log_anomaly/api/app.py#L166), [app.py](./backend/src/log_anomaly/api/app.py#L179), [app.py](./backend/src/log_anomaly/api/app.py#L194), [app.py](./backend/src/log_anomaly/api/app.py#L218)). Upload errors for unsupported extensions, oversize files, and ingestion failures have explicit HTTP statuses. Normalized analysis requests validate method, contamination, grouping window, and event count.

The health endpoint is process-level status only; it does not verify database readiness. The public `/docs` OpenAPI interface is enabled by FastAPI defaults. Expensive parsing and ML execute inline. No API auth, rate limit, job progress/cancellation, individual-event pagination, or retention/delete endpoint exists.

### SQLite

SQLite creates tables at initialization and stores event rows plus full event JSON per analysis ([sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L23), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L40), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L82)). The `analysis_events` table has no `analysis_id` relationship, while the history detail path reads the JSON copy. No migrations, indexes for the history ordering, retention, backup/restore, or multi-user boundary is implemented.

`list_alerts` loads recent analysis summaries, fetches and decodes each full analysis, then truncates the result ([sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L151)). This is costly as event/history volume grows; alert export is therefore not a scalable paginated query.

The Render manifest points SQLite at `data/log_anomaly.db` but declares no persistent disk ([render.yaml](./render.yaml#L18)). Durable history across host replacement/redeployment is not configured or verified.

### Performance concerns (not measured)

1. Upload bytes, decoded text, pandas records, result frames, serialized response, and export data can coexist in memory.
2. The async upload handler performs synchronous parsing, TF-IDF, Isolation Forest, DBSCAN, and SQLite work.
3. Clustering always runs; the baseline path can also fit an Isolation Forest whose scores are discarded.
4. No maximum upload-event count exists; DBSCAN/vectorization costs can grow with event count and vocabulary.
5. History detail/export return all events; alerts load many complete JSON analyses.
6. The dashboard filters and renders all event rows in the browser with no paging ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L265), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L602)).

No latency, throughput, memory, or concurrent-request measurements were taken. Benchmark these against declared deployment hardware before choosing production limits.

## Frontend/UI/UX

**Implemented:** a single responsive dashboard with upload, result summary, anomaly/normal/all filters, cluster filters, history, and PDF/XLSX/JSON/CSV export ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L335), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L494), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L602)). CSS includes responsive breakpoints and visible focus rules ([globals.css](./frontend/src/app/globals.css#L20), [globals.css](./frontend/src/app/globals.css#L224)).

**Gaps and misleading copy:**

- The dropzone says “Drop your file here,” but the component has no drag/drop handlers ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L365)).
- The interface labels unflagged predictions “CLEAN (Retained)” and calls the filter “Clean / Normal”; an unflagged prediction is not verified normal ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L430), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L610)).
- The row status says “Excluded” or “Retained” regardless of the export checkbox, which controls only export selection.
- Contamination is fixed at 10%; only grouping window is user-adjustable ([dashboard.tsx](./frontend/src/components/dashboard.tsx#L87), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L202)).
- The UI text describes multiple algorithms as if they were a combined auto detector; actual selection differs (BUG-05).
- The upload privacy copy says processing is local, although a configured frontend may send logs to a hosted API.
- There is no search, event pagination, upload progress/cancel, alert acknowledgement/ownership, or investigation lifecycle.
- `recharts` is declared in [package.json](./frontend/package.json#L12), but no chart component/import was found in the frontend source; visualization API routes are not consumed by the dashboard.
- No frontend test files or frontend test script were found. No browser-based visual or accessibility verification was performed.

## Security controls observed

**Positive controls:** file extensions are restricted; uploads are byte-bounded; PDF signatures/encryption/page count are checked; binary text is rejected; filenames are reduced to a basename; SQL values are parameterized; API request fields have bounds. No direct SQL-injection path was identified in the inspected queries.

These controls do not address the production blockers above. In particular, upload extension/size validation does not prevent high-row-count work, CORS does not authenticate, and identifier masking in the derived template does not sanitize stored messages.

## Testing, dependencies, and deployment

- Backend test source exists in [test_pipeline.py](./backend/tests/unit/test_pipeline.py), [test_api.py](./backend/tests/integration/test_api.py), and [test_project_setup.py](./backend/tests/unit/test_project_setup.py). Coverage includes parser examples, detector basics, grouping, persistence, uploads, exports, and API responses. Execution is unverified.
- No frontend test suite or app CI workflow was found. The only discovered GitHub workflow is in the separate `loghub/` checkout.
- Render declares free Python and Node web services ([render.yaml](./render.yaml#L1), [render.yaml](./render.yaml#L28)). The frontend build uses `npm install` rather than a lockfile-enforcing `npm ci` ([render.yaml](./render.yaml#L36)); Python dependency declarations use version ranges and no Python lockfile was found ([requirements.txt](./backend/requirements.txt), [pyproject.toml](./backend/pyproject.toml)).
- `NEXT_PUBLIC_API_BASE_URL` is a manually supplied Render environment variable ([render.yaml](./render.yaml#L42)); its deployed value was not verified.
- No Dockerfile/Compose file, application CI/CD, monitoring/alerting configuration, backup/restore runbook, or rollback evidence was found.
- No dependency vulnerability scan was run as part of this audit. Dependency security status is therefore **unassessed**, not “clean.”

## Prioritized implementation roadmap (for approval; no implementation started)

### P0 — Block unsafe public access

1. Keep the API private until authentication, authorization, tenant isolation, and access tests are in place.
2. Add server-side row/resource/rate/concurrency limits; ensure expensive work cannot starve health/read routes.
3. Neutralize formula-leading values in every spreadsheet export.
4. Set exact production CORS origins; define log redaction, retention, deletion, and access policy.

**Gate:** anonymous log access is denied; tenant-isolation and export-safety tests pass; hostile/high-volume requests are bounded.

### P1 — Correct detector, severity, and label contracts

1. Report the effective detector and avoid fitting unused models.
2. Decide whether severity rules are a supported feature; wire them into the common path or correct documentation.
3. Normalize label aliases and dataset-specific class semantics consistently across CSV ingestion, dashboard metrics, and visualization APIs.
4. Label current dashboard metrics as in-sample or replace them with a separate reproducible evaluation workflow.

**Gate:** API/UI method and severity labels match executed code; labeled fixtures verify known mappings; no metric is presented as held-out performance without a held-out protocol.

### P2 — Preserve source evidence and validate ML performance

1. Preserve raw records separately from normalized templates, with file digest, source location, and parser version.
2. Review dataset provenance, terms, privacy, and label semantics. The LogHub notice describes research/academic availability; confirm terms for the intended use ([loghub/LICENSE](./loghub/LICENSE#L3), [loghub/README.md](./loghub/README.md#L10)).
3. Run a real labeled, source/time-separated benchmark; document split, label mapping, threshold policy, confusion matrix, precision/recall/F1, and limitations. Do not use the random simulation endpoint as evidence.

**Gate:** independent rerun reproduces results from a documented dataset version and split; no synthetic labels are included in performance claims.

### P3 — Make persistence and operations supportable

1. Add schema migrations, retention/deletion, indexes, backups, restore tests, and durable storage for the selected deployment topology.
2. Replace full-history alert loading with bounded/paginated queries; add event pagination where needed.
3. Add CI for backend tests/lint and frontend lint/type/build; use deterministic dependency installation and vulnerability scanning.
4. Establish health/readiness semantics, monitoring, staging smoke checks, and rollback procedures.

**Gate:** clean-checkout CI is repeatable; restart/backup/restore and migration checks pass; resource and latency limits are measured on target hardware.

### P4 — Improve analyst workflow and support claims

1. Align upload copy/limits and detector terminology with actual behavior; distinguish “not flagged” from “normal.”
2. Add accessible search/filter/pagination, upload progress/cancel, and alert lifecycle only after identity and authorization design.
3. Integrate charts only when their metric meanings and label provenance are clear; add frontend tests.
4. Expand parser support only alongside representative fixtures and explicit unsupported-format behavior.

**Gate:** visible behavior, documentation, and API contracts agree; keyboard/accessibility and large-result workflows are validated.

## Final readiness decision

**Status: Not production-ready for untrusted users.** The current source is appropriate as a local prototype with trusted inputs and controlled access. Public exposure is blocked by unauthenticated access to stored log contents, lack of resource controls, and missing data-retention/privacy controls. The detector is implemented, but no verified benchmark establishes its accuracy or false-positive performance. The roadmap above is prioritized for approval; implementation has not begun.
