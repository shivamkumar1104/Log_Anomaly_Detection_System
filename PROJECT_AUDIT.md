# Log Anomaly Detection System — Repository Audit

**Audit date:** 2026-11-17  
**Scope:** Repository source, frontend, backend, tests, configuration, documentation, deployment manifest, and the bundled LogHub BGL sample.  
**Decision:** **NOT PRODUCTION READY**. This is a working local batch-analysis MVP, not a validated production service.

## Executive summary

The project has a functional Next.js dashboard connected to a FastAPI service. A local
production build, backend unit/API tests, lint checks, real BGL CSV upload, SQLite history
readback, and PDF/XLSX exports were exercised successfully. That validates a narrow
single-user workflow; it does not validate production deployment, security under hostile
traffic, large/concurrent workloads, or ML generalization.

The principal release blockers are unauthenticated access to log-bearing endpoints, no
parsed-row/rate/concurrency controls, storage of raw messages without retention/redaction,
spreadsheet formula injection, and poor results on a real labeled sample even in an
optimistic in-sample evaluation. The BGL CSV parser also loses all timestamps, hosts, and
services in the tested sample, invalidating time-based grouping and source attribution.

No application source, dependency, or deployment configuration was changed for this audit.
The existing user edits in [frontend/README.md](./frontend/README.md) and
[dashboard.tsx](./frontend/src/components/dashboard.tsx) were preserved. The six requested
reports are the only files changed for this audit.

## Architecture observed

```text
Browser: Next.js App Router / React / TypeScript
  └── dashboard: upload, client-side filters, history, exports
        └── FastAPI HTTP API
              ├── file validation, decoding, CSV/text/PDF parsing
              ├── pandas normalization and message-template masking
              ├── per-upload frequency baseline / TF-IDF + Isolation Forest / DBSCAN
              ├── host/service/template/time-window anomaly grouping
              ├── SQLite history and event JSON
              └── CSV/JSON/PDF/XLSX exports
```

The request path is in [api/app.py](./backend/src/log_anomaly/api/app.py#L116) and shared
scoring/grouping in [service.py](./backend/src/log_anomaly/service.py#L11). Severity rules
are implemented separately in [assess.py](./backend/src/log_anomaly/severity/assess.py#L13)
but are not called by that service. The API fits detectors for each upload; it does not load
the generated notebook artifact (see [backend/README.md](./backend/README.md#L20)).

## Verification actually performed

| Check | Result | Scope and limitation |
|---|---|---|
| Local frontend and backend | **PASS** | Frontend returned HTTP 200; `/api/health` returned HTTP 200 and `max_upload_mb: 100`. The dashboard had previously rendered “API connected.” |
| Backend automated tests | **PASS: 33 tests** | `pytest -p no:cacheprovider`, with a temporary SQLite path. One Starlette/httpx deprecation warning was emitted. |
| Backend Ruff | **PASS** | `ruff check --no-cache .` from `backend/`. |
| Frontend ESLint | **PASS** | `npm --prefix frontend run lint`. |
| Frontend production build | **PASS** | `npm --prefix frontend run build`; Next.js 16.4.6 / webpack compiled and statically generated `/` and `/_not-found`. Local Node was 26.12.1, not the Node 20.18.0 in Render configuration. |
| Real file upload and persistence | **PASS** | FastAPI TestClient uploaded the checked-in 2,000-row BGL CSV with an isolated temporary database. Upload, history/detail, PDF, and XLSX responses were HTTP 200. The temporary database was removed; existing user databases were not read or modified. |
| Labeled-data evaluation | **Exploratory only** | The same BGL sample was used to fit and score the detector. It is not a held-out test; see [ML_EVALUATION_REPORT.md](./ML_EVALUATION_REPORT.md). |
| Frontend dependency audit | **7 moderate findings** | Full `npm audit`: seven moderate transitive development-tool findings in the `@typescript-eslint` / `minimatch` tree; `npm audit --omit=dev`: zero production dependency findings. No dependency was changed. |
| Python dependency audit | **NOT VERIFIED** | `pip-audit` is not installed. No scanner was installed for this read-only audit. |
| Render deployment, backup/restore, load, concurrency, memory, CPU | **NOT VERIFIED** | No deployment or load test was run. The single BGL timing is not a load benchmark. |

## Workflow/functionality status

| Requested workflow | Status | Evidence-based assessment |
|---|---|---|
| 1. Application startup | **Verified locally** | Next development page and FastAPI health endpoint responded. Production deployment was not started. |
| 2. Frontend/backend connectivity | **Verified locally** | Dashboard health/history requests succeeded and displayed connected status. |
| 3. Log upload | **Verified, narrow** | Real BGL CSV upload endpoint succeeded in an isolated test database; browser upload was not separately replayed. |
| 4. Log parsing/preprocessing | **Partial** | 2,000 BGL rows parsed, but timestamp/host/service extraction failed for every row. |
| 5. Multiple log formats | **Partial** | CSV, common Apache access-log shape, Java-style starts, generic text, and text-based PDF have code paths. The test suite covers selected parser examples; broad vendor compatibility is not established. |
| 6–7. TF-IDF and Isolation Forest | **Implemented, unvalidated for generalization** | Per-file vectorization and deterministic Isolation Forest are in the analysis path; the API does not use a separately trained model artifact. |
| 8. Anomaly scores | **Implemented, file-relative** | Scores are scaled within each uploaded batch; they are not calibrated probabilities comparable across batches. |
| 9. Severity classification | **Partial** | Parsed source levels are preserved. YAML score-based severity rules exist but are not applied by `analyze_batch`. |
| 10. Alert grouping | **Partial; incorrect on BGL fields** | Grouping code exists; missing BGL timestamps/hosts/services collapse grouping to template-only keys with no time bound. |
| 11–12. History and persistence | **Verified locally** | Upload, history detail, and export worked in temporary SQLite. Durability, retention, migrations, and recovery are not verified. |
| 13. Search/filtering | **Partial** | Client-side anomaly/normal/all and cluster filters exist; text/time/severity search and pagination do not. |
| 14. Dashboard visualizations | **Partial** | Summary cards exist. No chart is rendered by the frontend; declared Recharts is not imported. |
| 15. Report exports | **Partial/verified** | PDF and XLSX endpoints passed the real-file test. Browser-side CSV/JSON exports exist; spreadsheet formula protection is absent. |
| 16. Error handling | **Partial** | Common upload validation errors have explicit HTTP responses. Dependency outages, database readiness, overload, and resource exhaustion are not comprehensively handled/tested. |

## Log-format compatibility

“Supported” below means a parser implementation exists, not universal compatibility. No
format accuracy percentage is asserted.

| Format | Status and implementation | Verified sample / limitations |
|---|---|---|
| Apache access log | **Partial support** — common access prefix in [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L20); a unit test checks host/timestamp/status severity. | Unit fixture passed; no broad Apache format corpus or accuracy rate measured. |
| Nginx | **Not separately implemented; partial prefix overlap** | Default access lines may match the Apache-shaped regex. No Nginx fixture was run; do not claim Nginx compatibility. |
| Java application | **Partial support** — timestamp/level regex and indented continuation handling. | Stack-trace merge unit test passed; layouts without the expected timestamp/level are generic text. |
| Python application | **Partial generic text only** | No dedicated Python formatter/parser; traceback boundaries are not guaranteed. |
| Linux system logs | **Partial generic text only** | No dedicated syslog/RFC3164 parser. Real BGL CSV labels loaded, but all 2,000 timestamps and all host/service values were null after normalization. |
| Windows Event Logs | **Unsupported as structured input** | No EVTX/XML event parser; accepted extensions are CSV, TXT, LOG, PDF. |
| JSON/JSONL | **Unsupported as structured input** | No JSON/JSONL upload extension or record parser. |
| CSV | **Partial, schema-dependent** | BGL upload preserved 2,000 rows, 143 alert labels, and severity values; timestamp/host/service extraction failed. Only recognized aliases are mapped. |
| Plain text | **Partial heuristic parser** | Generic lines can be retained; timestamps/severity are extracted only for recognized patterns. |
| Multiline stack traces | **Partial** | Java-style indented continuations are implemented and covered by a unit test; no comprehensive Python/other-language trace corpus was evaluated. |
| Text-based PDF | **Partial** | Text extraction and invalid/scanned PDF handling exist and are tested. Scanned PDFs require OCR and are rejected. |

The CSV detector returns confidence `1.0` from the `.csv` extension before validating its
schema ([parser.py](./backend/src/log_anomaly/ingestion/parser.py#L132)); this value is not a
measured parsing-accuracy score.

## Findings register

Every finding below includes severity, affected code, evidence, impact, fix, and acceptance
criteria. Related detailed reports: [security](./SECURITY_AUDIT.md),
[ML](./ML_EVALUATION_REPORT.md), [gaps](./MISSING_FEATURES.md), and
[roadmap](./IMPLEMENTATION_ROADMAP.md).

### SEC-01 — Log-bearing API is unauthenticated

- **Severity:** Critical if the Render service is deployed; public deployment status **NOT VERIFIED**.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L116), [render.yaml](./render.yaml#L1), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L130).
- **Evidence:** Upload, analysis history/detail, alerts, and exports have no auth/authorization dependency; Render declares web services. Detail/export return stored event messages.
- **Why it matters:** An unauthenticated caller can upload costly inputs or read another user's logs if the manifest is exposed publicly.
- **Recommended fix:** Keep private until identity, authorization, tenant boundaries, and access logging are designed and tested.
- **Acceptance criteria:** Anonymous access to every log-bearing endpoint is denied; authorized users can access only their tenant's records; security tests cover list/detail/export.

### SEC-02 — Spreadsheet exports allow formula-leading values

- **Severity:** High.
- **Affected files/modules:** [reports/export.py](./backend/src/log_anomaly/reports/export.py#L173), [api/app.py](./backend/src/log_anomaly/api/app.py#L224), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L67).
- **Evidence:** XLSX appends untrusted event values directly to cells; CSV implementations quote values but do not neutralize formulas.
- **Why it matters:** A spreadsheet application may interpret a log message beginning with formula syntax as an executable formula.
- **Recommended fix:** Centralize safe CSV/XLSX serialization and neutralize formula-leading text, including leading whitespace/control characters.
- **Acceptance criteria:** Tests cover `=`, `+`, `-`, `@`, whitespace/control-prefixed values in every export; benign values remain readable and exported cells are not formulas.

### SEC-03 — Upload workload is not bounded by parsed rows or request rate

- **Severity:** High.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L117), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L17), [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L32).
- **Evidence:** Upload reads up to the configured byte ceiling (100 MB local; Render sets 25 MB), then synchronously parses, vectorizes, clusters, scores, and persists; the file parser has no row cap or rate/concurrency control. The normalized-event JSON route separately caps at 10,000 rows.
- **Why it matters:** A compressed/compact high-row-count file or concurrent requests can consume memory/CPU and starve API workers.
- **Recommended fix:** Define and enforce event/token limits before expensive work; add rate and concurrency controls and explicit overload responses.
- **Acceptance criteria:** Tests prove byte/row/concurrency bounds, bounded memory on the supported workload, and responsive health checks while work is running.

### SEC-04 — Raw log messages persist without redaction or retention

- **Severity:** High.
- **Affected files/modules:** [normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L23), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L82), [api/app.py](./backend/src/log_anomaly/api/app.py#L185).
- **Evidence:** The normalized template masks a limited set of identifiers, but `message` remains raw; event rows and a full event JSON copy are stored. No deletion/retention policy exists.
- **Why it matters:** Logs may contain secrets or personal data; history and exports can retain them indefinitely.
- **Recommended fix:** Define redaction, raw-evidence access, retention/deletion, and encrypted-storage policy before public use.
- **Acceptance criteria:** Tests show sensitive fixtures are redacted according to policy, deletion removes all copies, and retention is enforced.

### SEC-05 — CORS trusts a broad hosted-origin pattern

- **Severity:** Medium; CORS is not authentication.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L35).
- **Evidence:** In addition to configured and localhost origins, the app allows `https?://.*\.onrender\.com`, credentials, all methods, and all headers.
- **Why it matters:** Browser-origin trust is broader than a single frontend origin; unauthenticated direct API access remains possible regardless of CORS.
- **Recommended fix:** Use only exact production origins; enable credentials only for an intentional auth/session design.
- **Acceptance criteria:** CORS tests allow the configured origin and reject unrelated Render/localhost origins in production configuration.

### DATA-01 — BGL timestamps and source identity are lost

- **Severity:** High for timeline/grouping; Medium for basic CSV acceptance.
- **Affected files/modules:** [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L44), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L258), [normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L27), [BGL sample](./loghub/BGL/BGL_2k.log_structured.csv).
- **Evidence:** On the real 2,000-row BGL sample, all 2,000 normalized timestamps, hosts, and services were null. The CSV has multiple timestamp-like columns and `Node`/`Component`; alias mapping overwrites earlier matches, does not map `Node`, and maps `Component` to `source`.
- **Why it matters:** The dashboard shows no time/source identity; grouping can merge same-template alerts across unrelated nodes and time periods.
- **Recommended fix:** Use deterministic column priorities and format-aware timestamp parsing; map dataset host/service fields and preserve raw content/row identifiers.
- **Acceptance criteria:** BGL fixture yields 2,000 rows, 2,000 valid timestamps, populated host/service where present, correct 143 labels, and no parsing warnings.

### DATA-02 — Format support and parser confidence are overstated

- **Severity:** Medium.
- **Affected files/modules:** [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L132), [backend/README.md](./backend/README.md#L1), [docs/architecture.md](./docs/architecture.md#L30).
- **Evidence:** Only common regex/alias cases are implemented; JSON, EVTX, and dedicated Nginx/Python/syslog parsers are absent. CSV extension alone yields confidence `1.0`; message selection prefers `EventTemplate`, so BGL raw `Content` is not retained as the primary message.
- **Why it matters:** Unsupported records can be accepted with missing fields or misleading confidence; source evidence may be lost.
- **Recommended fix:** Publish an explicit format contract, preserve raw records separately, and tie confidence to validated schema/format evidence.
- **Acceptance criteria:** Representative fixtures for every claimed format verify count, field extraction, multiline behavior, malformed-row policy, and documented limitations.

### ML-01 — BGL metric results are in-sample and poor

- **Severity:** High.
- **Affected files/modules:** [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L156), [ML_EVALUATION_REPORT.md](./ML_EVALUATION_REPORT.md).
- **Evidence:** Detector/vectorizer are fit on the complete uploaded file and scored on those same rows. On BGL, exploratory in-sample F1 was 0.1239 and recall 0.1538. Current UI correctly warns that its label metrics are not held-out.
- **Why it matters:** These metrics do not establish deployment performance; false negatives are high even on the in-sample run.
- **Recommended fix:** Keep UI figures explicitly descriptive and develop a reproducible time/source-separated benchmark with documented BGL label mapping and threshold selection.
- **Acceptance criteria:** Independent holdout results include confusion matrix, precision/recall/F1, FPR/FNR, latency, dataset/version, split, and reproducible commands.

### ML-02 — Severity rules and label contracts are disconnected

- **Severity:** Medium.
- **Affected files/modules:** [service.py](./backend/src/log_anomaly/service.py#L11), [assess.py](./backend/src/log_anomaly/severity/assess.py#L13), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L49), [visualization.py](./backend/src/log_anomaly/api/visualization.py#L62).
- **Evidence:** Shared upload analysis does not call `assess_severity`; CSV maps labels to `label`, while visualization metrics require `ground_truth`. Dashboard accepts only a limited binary label vocabulary, not BGL category tags.
- **Why it matters:** Severity is not score-derived as documented; labeled uploads can show no metrics or inconsistent metrics across endpoints.
- **Recommended fix:** Separate source severity from derived risk; define one canonical label schema and explicit dataset adapters.
- **Acceptance criteria:** Tests prove consistent source/derived severity and label mappings through upload, API metrics, and UI using known fixtures.

### ML-03 — No persisted training/inference model contract

- **Severity:** High for claims of trained-model inference; Medium for the current per-file MVP.
- **Affected files/modules:** [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63), [backend/README.md](./backend/README.md#L20), `backend/models/log_anomaly_isolation_forest.joblib` (local artifact, not tracked).
- **Evidence:** API fits a fresh vectorizer and detector per upload; it does not load the notebook artifact. No model version/rollback or stable feature vocabulary is used for future logs.
- **Why it matters:** The dashboard is not applying a previously trained production model; unseen-pattern generalization and model lifecycle are unverified.
- **Recommended fix:** Decide between explicitly per-file novelty scoring and a versioned train/serve model; document the contract and provenance.
- **Acceptance criteria:** A clean deployment can identify the exact model/vectorizer version, load it safely, reproduce inference, and roll back to a prior version—or the product explicitly remains per-file-only.

### DB-01 — Persistence duplicates events and has no lifecycle controls

- **Severity:** Medium.
- **Affected files/modules:** [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L23).
- **Evidence:** `analysis_events` and `analyses.events_json` both store event content; the event table has no `analysis_id` relationship and is not used for history detail. No explicit indexes, schema migrations, retention, or deletion API exists. `list_alerts` loads complete analyses one by one.
- **Why it matters:** Storage grows without cleanup; duplicated state can diverge; alert listing becomes increasingly expensive.
- **Recommended fix:** Use a versioned schema with analysis/event relationship, indexes, bounded queries, retention, and tested backup/restore.
- **Acceptance criteria:** Migration, referential integrity, paginated history/alerts, retention/deletion, and backup/restore tests pass on a disposable database.

### CFG-01 — Relative database path and unused environment variables

- **Severity:** Medium.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L27), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L164), [backend/.env.example](./backend/.env.example), [render.yaml](./render.yaml#L14).
- **Evidence:** The database default is relative to the process working directory. Both root `data/log_anomaly.db` and `backend/data/log_anomaly.db` exist with different metadata; contents were not inspected. `LOG_ANOMALY_DATABASE_URL`, `LOG_ANOMALY_ENV`, `LOG_ANOMALY_DATA_DIR`, and `LOG_ANOMALY_GROUP_WINDOW_MINUTES` are documented/configured but not consumed by backend source.
- **Why it matters:** Starting from different directories can silently split history; operators may believe ignored settings are active.
- **Recommended fix:** Resolve storage from an explicit absolute data directory and centralize typed settings; remove or implement unused options.
- **Acceptance criteria:** Startup from repository root and backend uses the same configured database; invalid/missing configuration fails visibly; every documented setting has a test.

### UI-01 — Missing investigation controls and misleading status language

- **Severity:** Medium.
- **Affected files/modules:** [dashboard.tsx](./frontend/src/components/dashboard.tsx#L380), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L563), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L627), [frontend/README.md](./frontend/README.md#L3).
- **Evidence:** Dropzone says “Drop your file” but only has file-input `onChange`; no drop handler. Rows label unflagged predictions “CLEAN” and filters say “Clean / Normal.” No text search, pagination, acknowledgement/resolve workflow, or charts appear in frontend source. README says users can adjust anomaly rate; the dashboard hard-codes `0.1`.
- **Why it matters:** Users may infer that unflagged records are verified normal; interaction/documentation promises are inaccurate, and large result sets are hard to investigate.
- **Recommended fix:** Use “not flagged,” align docs with actual controls, and prioritize accessible search/pagination and alert workflow after identity design.
- **Acceptance criteria:** UI labels distinguish prediction from ground truth; all visible interactions work; documented controls match the page; keyboard/mobile checks pass.

### UI-02 — Local-processing privacy copy can be misleading

- **Severity:** Medium.
- **Affected files/modules:** [dashboard.tsx](./frontend/src/components/dashboard.tsx#L424), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L7).
- **Evidence:** UI says files are processed locally by “your backend,” but `NEXT_PUBLIC_API_BASE_URL` can target a hosted service.
- **Why it matters:** Users may not understand where sensitive log data is sent.
- **Recommended fix:** Display the configured destination/privacy boundary explicitly and require an operator disclosure for remote endpoints.
- **Acceptance criteria:** Local and remote configurations show truthful processing/storage notices before upload.

### OPS-01 — Operational deployment controls are absent or unverified

- **Severity:** High for production readiness.
- **Affected files/modules:** [render.yaml](./render.yaml), `deployment/` (placeholder only), application workflows.
- **Evidence:** Render Free services are configured, but no persistent disk, application CI workflow, Dockerfile/Compose, monitoring, backup/restore, staging, or rollback evidence was found. The only workflow is the separate LogHub crawler.
- **Why it matters:** SQLite durability across replacement/redeploy, production health, recovery, and reproducible releases are not established.
- **Recommended fix:** Select durable storage and runtime topology; add application CI, monitoring, backup/restore, and tested rollout/rollback.
- **Acceptance criteria:** Deployment smoke tests pass on target runtime; restart preserves data; restore and rollback are exercised; CI gates all supported versions.

### DEP-01 — Dependency risk is only partially assessed

- **Severity:** Medium (audit gap); frontend finding itself is Moderate.
- **Affected files/modules:** [frontend/package-lock.json](./frontend/package-lock.json), [backend/requirements.txt](./backend/requirements.txt), [backend/pyproject.toml](./backend/pyproject.toml).
- **Evidence:** Full npm audit found seven moderate transitive development dependency findings, including minimatch GHSA-g3hv-75wg-m249; production-only npm audit found zero. `pip-audit` was unavailable, so Python CVE status is NOT VERIFIED. No dependency changes were made.
- **Why it matters:** Backend dependency exposure and remediation status remain unknown.
- **Recommended fix:** After approval, update affected frontend dev tooling in a separate dependency task; run a Python vulnerability scanner against the resolved deployment environment.
- **Acceptance criteria:** CI records dependency audit results for locked frontend and resolved Python dependencies; no unresolved high/critical issue; moderate findings are documented or remediated.

### CODE-01 — Duplicate/placeholder modules and debug utilities

- **Severity:** Low.
- **Affected files/modules:** [simulation.py](./backend/src/log_anomaly/visualization/simulation.py), [simulations.py](./backend/src/log_anomaly/visualization/simulations.py), `features/`, `templates/`, `config/`, root debug import scripts.
- **Evidence:** `simulation.py` and `simulations.py` contain duplicate synthetic generators; API imports only the singular module. The named feature/template/config packages are `__init__.py` stubs; three root scripts repeat import-debug behavior.
- **Why it matters:** Dead/duplicate code makes ownership and intended public APIs unclear.
- **Recommended fix:** After approval, select one canonical module and remove or document unused scaffolding/debug scripts; do not mistake stubs for implemented architecture.
- **Acceptance criteria:** Static import/reference check shows one canonical generator and no undocumented runtime feature claims.

## Frontend/UI, testing, and accessibility

The dashboard has responsive CSS breakpoints, visible keyboard focus styling, upload states,
error banners, cluster/anomaly filters, history, and export controls
([globals.css](./frontend/src/app/globals.css#L27),
[dashboard.tsx](./frontend/src/components/dashboard.tsx#L361)). This is a working MVP
interface, not a full alert-management product. Accessibility, screen-reader behavior, and
mobile interaction are **NOT VERIFIED**; no frontend component test suite was found. Recharts is declared
but not imported; the backend visualization routes are not consumed by the dashboard.

## Security conclusions

Basic controls observed include extension allowlisting, byte limits, PDF checks, filename
basename normalization, bounded normalized-event request length, and parameterized SQLite
queries. No direct SQL injection, path traversal write, or `dangerouslySetInnerHTML` use was
identified in inspected app source. These do not resolve unauthenticated log access,
spreadsheet formula injection, raw-message retention, or missing workload controls. CSRF is
not currently based on a cookie-session design; it must be reassessed if that auth design is
introduced. A complete secret-history scan and Python dependency advisory scan were not run.

## Production-readiness score

| Rubric category | Score | Evidence-based rationale |
|---|---:|---|
| Architecture and code quality | **7 / 15** | Modular FastAPI/service/persistence layers and typed requests; offset by unused stubs/duplicate code, relative DB paths, and config mismatches. |
| Frontend and user experience | **5 / 10** | Functional responsive dashboard, file selection, filters/history/exports; no alert lifecycle/search/pagination/charts, and “clean” terminology is misleading. |
| Backend and API reliability | **8 / 15** | Health/upload/history/export routes and passing API tests; actual BGL path works, but no auth/row bounds, synchronous workload, and DB readiness is not part of health. |
| Machine-learning correctness | **3 / 20** | TF-IDF/Isolation Forest and deterministic scoring exist; no held-out benchmark, BGL in-sample recall is low, training artifact is unused, and severity is disconnected. |
| Data engineering and log compatibility | **4 / 10** | CSV/Apache/Java/text/PDF paths; tested BGL loses all timestamps/host/service and JSON/EVTX are unsupported. |
| Security | **2 / 15** | Some input/query protections; critical public-access risk, raw log retention, spreadsheet formulas, broad CORS, and no rate/tenant controls. |
| Testing, deployment, monitoring | **6 / 15** | 33 backend tests, Ruff, ESLint, production build and local endpoints passed; no application CI, actual deployment, persistent storage, monitoring, recovery, or Python CVE scan. |
| **Total** | **35 / 100** | A low score does not replace the critical security release gate. |

## Final verdict

**NOT PRODUCTION READY.** The source is a locally runnable batch-analysis MVP. Do not expose
the Render backend to untrusted users until authentication/tenant isolation, upload resource
controls, safe exports, privacy/retention, durable storage, and independent ML validation are
implemented and verified. No implementation was started; approval is required before source
changes.
