# Production Readiness Report

**Audit date:** 2026-11-17  
**Overall score:** **35 / 100**  
**Verdict:** **NOT PRODUCTION READY**

## Executive decision

The project is a working local batch-analysis MVP. The local frontend/backend workflow, a
real BGL CSV upload through FastAPI, temporary SQLite persistence/readback, and PDF/XLSX
exports succeeded. Backend tests, Ruff, frontend ESLint, and the Next.js production build
also passed.

Those checks do not establish safe public operation. The configured Render web service has
unauthenticated log-bearing routes, no row/rate/concurrency controls, no configured durable
SQLite disk, and no backup/recovery or monitoring. The detector has no independent holdout
benchmark; its exploratory same-batch BGL evaluation yielded 0.1239 F1 and 0.1538 recall.
Do not treat this report's score as a release approval.

## Readiness score

| Category | Score | Evidence and justification |
|---|---:|---|
| Architecture and code quality | **7 / 15** | Shared service and modular packages exist ([service.py](./backend/src/log_anomaly/service.py#L11)); tests and static checks pass. Relative DB locations/config options, stubs, duplicate simulation modules, and duplicate event storage reduce confidence. |
| Frontend and user experience | **5 / 10** | Responsive dashboard and local integration work; upload/history/export are present. No chart rendering, search, pagination, alert acknowledgement/resolution, or frontend test suite. “Clean” may overstate an unflagged prediction. |
| Backend and API reliability | **8 / 15** | FastAPI health/upload/history/detail/alerts/export routes exist and passed tests plus an isolated BGL workflow. No auth, upload row limit, rate/concurrency control, background processing, or DB-aware readiness check. |
| Machine-learning correctness | **3 / 20** | TF-IDF, Isolation Forest, a frequency baseline, and repeatable seed exist. There is no independent test set or deployed model artifact; same-sample BGL results show high false-negative rate and are not generalization evidence. |
| Data engineering and log compatibility | **4 / 10** | Several parser paths exist; BGL's 2,000 rows and labels were retained. All BGL timestamps/hosts/services were lost; several requested formats are unsupported or only heuristic. |
| Security | **2 / 15** | File byte/type checks and parameterized SQL exist. Critical unauthenticated access, raw message persistence, formula injection, broad CORS, and missing resource controls are blockers. |
| Testing, deployment, monitoring | **6 / 15** | 33 backend tests, Ruff, ESLint, local endpoints, and frontend production build passed. Render deployment, Python dependency audit, load/concurrency, persistent storage, observability, backups, restore, and rollback are NOT VERIFIED or absent. |
| **Total** | **35 / 100** | **NOT PRODUCTION READY** |

### Score interpretation

The score reflects the application as inspected, not the percentage of work complete.
Critical security risk independently blocks production regardless of numeric score.
Detailed evidence appears in [PROJECT_AUDIT.md](./PROJECT_AUDIT.md) and
[SECURITY_AUDIT.md](./SECURITY_AUDIT.md).

## Verified and unverified operations

| Area | Result |
|---|---|
| Frontend / backend local startup | Both returned HTTP 200; health reported a 100 MB configured upload limit. |
| Backend tests | 33 passed using a temporary SQLite database; one Starlette/httpx deprecation warning. |
| Backend Ruff | Passed with `ruff check --no-cache .`. |
| Frontend lint | Passed with `npm --prefix frontend run lint`. |
| Frontend production build | Passed on local Node 26.12.1 with Next.js 16.4.6; Render specifies Node 20.18.0. |
| Real BGL upload | 2,000-row public LogHub CSV posted successfully; history/detail, PDF, and XLSX each returned HTTP 200. Database was isolated and removed. |
| ML generalization | NOT VERIFIED. Only an in-sample exploratory result was computed; see [ML_EVALUATION_REPORT.md](./ML_EVALUATION_REPORT.md). |
| Render production deployment | NOT VERIFIED; no deploy was initiated. |
| Performance/load | NOT VERIFIED beyond one 2,000-row in-process timing. No memory, CPU, concurrent-upload, medium/large-file, or production API latency benchmark. |
| Python dependency advisories | NOT VERIFIED (`pip-audit` unavailable); no scanner installed. Full frontend `npm audit` found 7 moderate dev-tool dependency findings; production-only audit found 0. |

## Release-blocking findings

### PROD-01 — Public log access without authentication or tenant boundary

- **Severity:** Critical if deployed publicly.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L116), [render.yaml](./render.yaml#L1), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L130).
- **Evidence:** Upload, history/detail, alert, and export routes do not require authentication; configured Render services are web services.
- **Why it matters:** A caller can upload work and retrieve persisted logs from other users if the service is exposed.
- **Recommended fix:** Keep private until identity, authorization, tenant-scoped persistence, and access logging are designed and tested.
- **Acceptance criteria:** Anonymous access is denied on every log-bearing endpoint; cross-tenant access tests pass for list/detail/alerts/export.

### PROD-02 — Unbounded processing work and no overload controls

- **Severity:** High.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L117), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L17), [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L32).
- **Evidence:** File bytes are bounded, but parsed CSV rows are not; analysis and DBSCAN execute synchronously in the upload request. No rate/concurrency limits exist.
- **Why it matters:** Large or simultaneous requests can exhaust process resources and impact unrelated users/health checks.
- **Recommended fix:** Define supported workloads; enforce byte, row, vocabulary, time, and concurrency limits; return explicit overload responses.
- **Acceptance criteria:** Adversarial/high-row inputs stop at documented bounds; concurrent tests stay within target memory/latency and health remains responsive.

### PROD-03 — Data retention and durability are undefined

- **Severity:** High.
- **Affected files/modules:** [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L82), [render.yaml](./render.yaml#L18).
- **Evidence:** Raw event messages and JSON copies are stored without retention/deletion. Render points at a relative SQLite file but declares no persistent disk, backup, or restore.
- **Why it matters:** Sensitive logs may be retained indefinitely and may be lost on service replacement.
- **Recommended fix:** Define retention/deletion and encrypted storage; choose managed durable storage or explicitly provision and test persistent disk/backup/restore.
- **Acceptance criteria:** Retention and deletion cover every copy; restart/redeploy preserves expected data; backup restore is exercised and measured.

### PROD-04 — Real-data parser fields break correlation

- **Severity:** High for alert grouping and timeline accuracy.
- **Affected files/modules:** [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L258), [normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L27), [correlate.py](./backend/src/log_anomaly/grouping/correlate.py#L36).
- **Evidence:** BGL sample normalization yielded zero valid timestamps, hosts, and services across 2,000 rows; all 212 flagged rows grouped into only 20 template-only groups, largest group 51 events.
- **Why it matters:** Events from distinct nodes/times can be presented as one incident; timeline and source attribution are unavailable.
- **Recommended fix:** Resolve alias priority, timestamp format parsing, and BGL host/service mapping; preserve source columns.
- **Acceptance criteria:** BGL fixture yields correct timestamp/host/service fields and grouping tests demonstrate unrelated events are not merged.

### PROD-05 — ML quality and model lifecycle are not established

- **Severity:** High.
- **Affected files/modules:** [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63), [backend/README.md](./backend/README.md#L20).
- **Evidence:** Detector fits and scores one upload; notebook artifact is not loaded by API. In-sample BGL evaluation produced 0.1038 precision, 0.1538 recall, 0.1239 F1, and 0.8462 FNR.
- **Why it matters:** No evidence supports incident-detection claims on future logs; severe missed-alert risk is plausible.
- **Recommended fix:** Define detector mode and model lifecycle, then evaluate on time/source-separated ground-truth data before setting thresholds.
- **Acceptance criteria:** Independent benchmark is reproducible and includes confusion matrix, PR/F1, FPR/FNR, latency, throughput, dataset version, and threshold policy.

### PROD-06 — Spreadsheet export is not safe for untrusted log values

- **Severity:** High.
- **Affected files/modules:** [reports/export.py](./backend/src/log_anomaly/reports/export.py#L178), [api/app.py](./backend/src/log_anomaly/api/app.py#L224).
- **Evidence:** Log values are appended directly into XLSX cells or CSV; quoting alone is not formula neutralization.
- **Why it matters:** Opening a malicious event in a spreadsheet may execute a formula.
- **Recommended fix:** Neutralize formula-leading text in every CSV/XLSX exporter and test hostile values.
- **Acceptance criteria:** Formula-prefixed or whitespace-prefixed cells are exported as inert text across all export paths.

## Minimum production gates

1. **Security:** authentication/authorization, tenant isolation, exact CORS, safe exports,
   rate/concurrency/row bounds, privacy and retention policy, and a reviewed dependency
   posture.
2. **Data correctness:** representative parser fixtures for every claimed format; BGL
   timestamp/host/service/label contract; explicit malformed-record behavior.
3. **ML:** held-out, reproducible, source/time-separated evaluation and a documented
   false-positive/false-negative operating point; no synthetic-label evidence.
4. **Reliability:** durable database and migrations, retention/deletion, backup/restore,
   structured logs, monitoring, readiness, CI and tested rollback.
5. **Capacity:** define workload/SLOs, then measure small/medium/large uploads and
   concurrency on the actual deployment runtime and hardware.

## Final verdict

**NOT PRODUCTION READY.** The application can run locally and complete a bounded workflow,
but no public deployment should be approved until the Critical/High findings above are
resolved and their acceptance criteria are independently verified.
