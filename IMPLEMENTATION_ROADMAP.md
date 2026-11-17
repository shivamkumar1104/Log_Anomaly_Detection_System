# Implementation Roadmap — For Approval

**Status:** Proposed only. No application implementation has started.  
**Audit date:** 2026-11-17  
**Release verdict:** **NOT PRODUCTION READY**

This sequence prioritizes safety and evidence over feature expansion. Do not expose the
service publicly until Phase 0 acceptance criteria pass. Scope and implementation details
remain subject to user approval.

## P0 — Establish a safe trust boundary

### P0.1 Authentication, authorization, and tenant isolation

- **Severity:** Critical.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L116), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L130), [render.yaml](./render.yaml#L1).
- **Evidence:** Upload, history/detail, alert, and export routes are unauthenticated; Render config describes web services.
- **Why it matters:** Public access could expose other users' log contents and allow expensive submissions.
- **Recommended fix:** Keep private; select identity/session strategy and tenant data model before implementing route authorization.
- **Acceptance criteria:** Anonymous access is denied; tenant scoping is enforced in all reads/exports; tests cover ID enumeration and cross-tenant access; deployment config does not publish an unsecured backend.
- **Dependency:** None; must precede public deployment and alert lifecycle.

### P0.2 Bound upload and analysis resources

- **Severity:** High.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L117), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L17), [cluster.py](./backend/src/log_anomaly/grouping/cluster.py#L12).
- **Evidence:** Byte limits exist, but uploaded rows, request rate, and concurrency are not limited; CPU-heavy work is synchronous.
- **Why it matters:** High-row-count or simultaneous uploads can consume memory/CPU and make the service unavailable.
- **Recommended fix:** Agree supported file/row sizes, per-user rate and concurrency bounds, processing timeout, and overload response before choosing synchronous or job-queue architecture.
- **Acceptance criteria:** Oversize byte/row/rate/concurrency cases are rejected predictably; supported workload meets agreed latency/memory budget; health remains responsive during processing.
- **Dependency:** Authentication/identity design informs per-user limits; basic global limits can be tested independently.

### P0.3 Make exported spreadsheets safe

- **Severity:** High.
- **Affected files/modules:** [reports/export.py](./backend/src/log_anomaly/reports/export.py#L178), [api/app.py](./backend/src/log_anomaly/api/app.py#L224), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L67).
- **Evidence:** Raw values are written to CSV/XLSX without formula neutralization.
- **Why it matters:** An analyst opening a report can execute a formula embedded in an untrusted log message.
- **Recommended fix:** Centralize CSV/XLSX-safe serialization and preserve raw evidence only in the controlled storage path.
- **Acceptance criteria:** Tests cover formula prefixes and leading whitespace/control characters for browser/API CSV and XLSX; exported cells remain inert text.
- **Dependency:** None.

### P0.4 Define log privacy, retention, and CORS policy

- **Severity:** High (data handling); Medium (CORS).
- **Affected files/modules:** [normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L23), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L82), [api/app.py](./backend/src/log_anomaly/api/app.py#L35).
- **Evidence:** Original messages persist without retention/deletion; the template mask is limited; CORS allows a broad Render-origin pattern with credentials.
- **Why it matters:** Logs may contain secrets/PII and be retained indefinitely; browser trust is broader than required.
- **Recommended fix:** Decide redaction/raw-evidence rules, retention/deletion/encryption, and exact production origins before handling untrusted customer logs.
- **Acceptance criteria:** Deletion/expiry removes all event copies; sensitive fixture tests pass; production CORS allows only approved origins; no secrets are copied into reports.
- **Dependency:** Tenant identity from P0.1 for per-user retention/access.

## P1 — Correct source data and ML contracts

### P1.1 Repair CSV field and timestamp mapping

- **Severity:** High.
- **Affected files/modules:** [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L258), [normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L27), [correlate.py](./backend/src/log_anomaly/grouping/correlate.py#L16).
- **Evidence:** Real BGL sample loses every timestamp, host, and service; flagged records collapse into 20 template-only groups.
- **Why it matters:** Alert correlation can merge unrelated nodes/times and time-series features are unavailable.
- **Recommended fix:** Deterministic alias precedence; explicit timestamp format parsing; map dataset `Node`/`Component`; retain `Content`, `EventId`, and source-row identity.
- **Acceptance criteria:** Real BGL fixture yields all 2,000 records, valid timestamps, correctly mapped host/service/labels, no warnings; grouping tests prove unrelated sources/times stay separate.
- **Dependency:** None.

### P1.2 Define format and label schemas

- **Severity:** Medium.
- **Affected files/modules:** [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L33), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L62), [visualization.py](./backend/src/log_anomaly/api/visualization.py#L62).
- **Evidence:** CSV parser maps labels to `label`, visualization API requires `ground_truth`, and dashboard handles only a limited binary vocabulary. JSON/JSONL and EVTX are unsupported; CSV extension gives confidence 1.0.
- **Why it matters:** Metrics can disappear or disagree; UI/README can imply unsupported format coverage.
- **Recommended fix:** Establish canonical event/label contracts and explicit parser adapters; define confidence semantics and preserve raw records.
- **Acceptance criteria:** Every claimed format has a representative fixture with timestamp/severity/host/label/malformed/multiline assertions; all evaluation routes consume the same canonical labels.
- **Dependency:** P1.1 for BGL-specific fields.

### P1.3 Decide and verify the detector contract

- **Severity:** High.
- **Affected files/modules:** [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L14), [backend/README.md](./backend/README.md#L20), [service.py](./backend/src/log_anomaly/service.py#L11).
- **Evidence:** API fits per upload and ignores notebook artifact; metrics are same-batch; severity assessor is not called.
- **Why it matters:** Training/inference claims, model identity, severity, and detection quality are not established.
- **Recommended fix:** Choose either documented per-file novelty scoring or a versioned train/serve model; make effective detector/severity behavior explicit.
- **Acceptance criteria:** Response/UI identify actual scoring mode; reproducible time/source-separated holdout is run on a permitted labeled dataset; confusion matrix, precision/recall/F1, FPR/FNR, threshold policy, and limitations are reported.
- **Dependency:** P1.1/P1.2 for reliable fields/labels; P0 privacy and access policy before external datasets contain sensitive data.

### P1.4 Add false-positive and analyst feedback policy

- **Severity:** Medium.
- **Affected files/modules:** [dashboard.tsx](./frontend/src/components/dashboard.tsx#L627), [api/app.py](./backend/src/log_anomaly/api/app.py#L218).
- **Evidence:** No acknowledgement/resolve/suppress/feedback workflow; non-flagged predictions are labeled “CLEAN.”
- **Why it matters:** Analysts cannot correct repeated noise, and the UI presents a prediction as confirmed truth.
- **Recommended fix:** Rename status to “Not flagged” and design review/feedback semantics after auth and tenant scope.
- **Acceptance criteria:** UI distinguishes prediction from ground truth; authorized feedback actions persist and have audit history; suppression cannot silently hide critical evidence.
- **Dependency:** P0.1.

## P2 — Make data storage and operations durable

### P2.1 Resolve database location, schema, and query lifecycle

- **Severity:** Medium.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L27), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L23).
- **Evidence:** CWD-relative DB path can split history; event rows and analysis JSON duplicate data; no migrations/indexes/retention/pagination; alert listing loads complete analyses.
- **Why it matters:** Storage grows, records can diverge, and query cost increases; deployment persistence is not reliable.
- **Recommended fix:** Select supported topology (single-instance SQLite on durable storage or managed database), use explicit absolute config, migrations, relationships, indexes, bounded queries, and retention.
- **Acceptance criteria:** Startup from documented directories selects one location; migrations are repeatable; paginated history/alerts and deletion tests pass; restart/backup/restore preserve expected records.
- **Dependency:** P0.1 tenant design and P0.4 retention policy.

### P2.2 Establish deployment observability and recovery

- **Severity:** High for production readiness.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L109), [render.yaml](./render.yaml), `deployment/`.
- **Evidence:** Health reports process status only; Render Free has no declared persistent disk; no application CI, monitoring, backup/restore, or rollback evidence.
- **Why it matters:** Operators cannot verify dependency readiness, detect service degradation, or restore data/release safely.
- **Recommended fix:** Define health/readiness, structured redacted logs, metrics/alerts, deployment workflow, backup/restore, and rollback for selected hosting.
- **Acceptance criteria:** Staging deploy verifies frontend/backend integration; readiness detects DB failures; alerts fire for agreed failures; restore and rollback are rehearsed.
- **Dependency:** P2.1 storage choice.

## P3 — Improve analyst experience and regression coverage

### P3.1 Align copy and actual controls

- **Severity:** Medium.
- **Affected files/modules:** [dashboard.tsx](./frontend/src/components/dashboard.tsx#L380), [frontend/README.md](./frontend/README.md#L3).
- **Evidence:** Dropzone implies drag/drop without drop handlers; README says anomaly rate is adjustable while UI hard-codes 0.1; remote API configuration can conflict with “processed locally” copy.
- **Why it matters:** Users may expect nonexistent controls or misunderstand where logs are sent.
- **Recommended fix:** Make copy match implemented controls and disclose configured processing destination.
- **Acceptance criteria:** Manual UI review verifies each promise, including local vs remote endpoint copy and keyboard file selection.
- **Dependency:** P0.4 privacy decision.

### P3.2 Add scalable investigation and visualizations

- **Severity:** Medium.
- **Affected files/modules:** [dashboard.tsx](./frontend/src/components/dashboard.tsx#L563), [package.json](./frontend/package.json#L12), [visualization.py](./backend/src/log_anomaly/api/visualization.py#L62).
- **Evidence:** No text search/pagination/alert lifecycle/chart rendering; Recharts is unused; backend visualization API is not connected to the page.
- **Why it matters:** Full-result client rendering and limited filters impede investigation as data grows.
- **Recommended fix:** Add server-side search/pagination and alert state first; integrate charts only after metric contracts are verified.
- **Acceptance criteria:** Large-result UI remains responsive; search/pagination results match API; chart values have tested definitions and accessible alternatives.
- **Dependency:** P0.1 and P1.2.

### P3.3 Add frontend behavior/accessibility tests

- **Severity:** Medium.
- **Affected files/modules:** [frontend/package.json](./frontend/package.json), [frontend/src/components/dashboard.tsx](./frontend/src/components/dashboard.tsx), [globals.css](./frontend/src/app/globals.css).
- **Evidence:** No frontend test source/script was found; accessibility and mobile behavior were not formally tested.
- **Why it matters:** Build/lint do not prove upload, error, empty, keyboard, screen-reader, and mobile interactions work.
- **Recommended fix:** Add focused tests for user-visible workflows and an accessibility/mobile check after UI requirements are agreed.
- **Acceptance criteria:** Tests cover upload validation/progress/error, history empty/error/open, filters, exports, keyboard navigation, and responsive layout.
- **Dependency:** None.

## P4 — Supply-chain and final release gate

### P4.1 Complete dependency review

- **Severity:** Medium audit gap.
- **Affected files/modules:** [frontend/package-lock.json](./frontend/package-lock.json), [backend/requirements.txt](./backend/requirements.txt), [backend/pyproject.toml](./backend/pyproject.toml).
- **Evidence:** Frontend full audit shows seven moderate transitive dev findings; production-only audit is clean; Python scan not run because `pip-audit` is absent.
- **Why it matters:** Python dependency exposure is unknown and the frontend toolchain has known advisories.
- **Recommended fix:** After approval, resolve frontend issues in an isolated dependency task and audit resolved Python packages without exposing secrets.
- **Acceptance criteria:** Both ecosystems are audited in CI; no unresolved high/critical issue; exceptions are documented and rechecked.
- **Dependency:** User approval for dependency changes; no upgrade is authorized by this audit.

### P4.2 Run target-environment acceptance and capacity tests

- **Severity:** High release gate.
- **Affected files/modules:** [render.yaml](./render.yaml), API upload path, parser, SQLite storage.
- **Evidence:** Local build/tests pass, but local Python 3.14/Node 26 differ from Render Python 3.11.9/Node 20.18.0; only one 2,000-event timing was measured.
- **Why it matters:** Runtime compatibility, deployment behavior, load capacity, and operational SLOs remain unverified.
- **Recommended fix:** Run the full validation matrix on the exact deployment runtime and actual configured storage.
- **Acceptance criteria:** Startup/smoke tests, supported file sizes, small/medium/large row counts, concurrent uploads, CPU/RAM, API p50/p95, persistence/restart, backup/restore, and rollback satisfy approved SLOs.
- **Dependency:** P0–P2 gates; target hardware and workload must be agreed before setting numeric SLOs.

## Proposed approval sequence

1. Approve scope and risk policy; keep public deployment disabled.
2. Implement and independently test P0 security controls.
3. Correct BGL/parser/label contracts and decide model mode (P1).
4. Choose storage/deployment topology and add operational recovery (P2).
5. Add analyst workflow and frontend regression checks (P3).
6. Resolve dependency audit findings only with explicit upgrade approval; run target-runtime
   release gate (P4).

**No code changes, deletion, or dependency upgrades are included in this roadmap.** The
implementation should begin only after user approval.
