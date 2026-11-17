# Security Audit

**Audit date:** 2026-11-17  
**Scope:** FastAPI routes, upload/parsing, persistence, exports, CORS, frontend data flow,
deployment configuration, and dependency advisories. This is a repository assessment, not
proof that a remote Render deployment exists.

## Executive summary

**Security verdict: NOT SAFE FOR PUBLIC/UNTRUSTED USE.** The Render manifest describes web
services, while upload, history, alerts, detail, and export endpoints have no authentication
or authorization. Logs are retained unredacted, upload work has no row/rate/concurrency
bound, and XLSX/CSV exports do not neutralize formula-leading values.

No source or dependency was changed. No actual user database contents or credentials are
included in this report.

## Findings

### SEC-01 — Unauthenticated access to stored log data

- **Severity:** **Critical** if the backend is public.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L116), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L130), [render.yaml](./render.yaml#L1).
- **Evidence:** Route handlers for `/api/upload`, `/api/analyses`, `/api/analyses/{id}`, `/api/alerts`, and exports have no auth/authorization dependency. Detail returns full event JSON; exports include messages. Render declares web services, but deployment state was not checked.
- **Why it matters:** Anonymous users could submit workloads and enumerate/read stored records if the service is deployed as configured. There is no user/tenant boundary.
- **Recommended fix:** Keep the service private. Add identity, authorization on every data route, tenant-scoped queries, audit logging, and least-privilege storage before public access.
- **Acceptance criteria:** Unauthenticated requests are denied; authorization tests prove a user cannot access another tenant's analyses, alerts, or exports; health reveals no sensitive data.

### SEC-02 — Formula injection in CSV/XLSX output

- **Severity:** **High**.
- **Affected files/modules:** [reports/export.py](./backend/src/log_anomaly/reports/export.py#L173), [api/app.py](./backend/src/log_anomaly/api/app.py#L224), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L67).
- **Evidence:** Event fields are appended directly to XLSX cells; API and browser CSV use ordinary serialization/quoting. No formula-leading character neutralization is present.
- **Why it matters:** A log line beginning with spreadsheet formula syntax may execute when an analyst opens the exported file.
- **Recommended fix:** Apply one safe export encoder to every CSV/XLSX route. Neutralize `=`, `+`, `-`, and `@` after leading whitespace/control characters while preserving original evidence in access-controlled storage.
- **Acceptance criteria:** Unit tests cover formula prefixes, whitespace/control prefixes, Unicode, and benign values for every exporter; generated spreadsheets contain no formula cells derived from untrusted input.

### SEC-03 — Resource exhaustion / denial-of-service exposure

- **Severity:** **High**.
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L117), [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L17), [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L32), [cluster.py](./backend/src/log_anomaly/grouping/cluster.py#L12).
- **Evidence:** The upload handler reads up to the configured byte ceiling (100 MB local; 25 MB in Render config) and performs synchronous parse, vectorization, Isolation Forest, DBSCAN, persistence, and full-result serialization. File uploads have no row cap, rate limit, or concurrency limit. The separate JSON analysis endpoint is capped at 10,000 records.
- **Why it matters:** Small byte size does not bound CSV row count, vocabulary, token processing, serialized response size, or concurrent CPU/RAM use.
- **Recommended fix:** Add server-side row/token/request limits, rate/concurrency control, timeouts, and explicit overload behavior. Move long-running work to a bounded job system only if the supported workload requires it.
- **Acceptance criteria:** Limits are enforced before expensive work; hostile row counts and concurrent requests cannot starve health checks or exceed documented resource budgets.

### SEC-04 — Sensitive log contents are stored without redaction or deletion

- **Severity:** **High**.
- **Affected files/modules:** [normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L23), [sqlite_store.py](./backend/src/log_anomaly/persistence/sqlite_store.py#L82), [api/app.py](./backend/src/log_anomaly/api/app.py#L185).
- **Evidence:** Template normalization masks a limited set of identifiers but preserves the original message. SQLite stores event rows and an `events_json` copy; no retention/deletion endpoint or policy is implemented.
- **Why it matters:** Logs commonly contain credentials, identifiers, and internal topology. Masking the template does not sanitize the persisted message or export.
- **Recommended fix:** Define field-level redaction, raw evidence access, retention/deletion, encryption, and backup controls. Avoid keeping duplicate unbounded copies.
- **Acceptance criteria:** Sensitive test values are redacted according to policy; retention deletes all copies and exports; access is tenant-scoped and auditable.

### SEC-05 — Broad credentialed CORS rule

- **Severity:** **Medium** (defense-in-depth; not an auth boundary).
- **Affected files/modules:** [api/app.py](./backend/src/log_anomaly/api/app.py#L35).
- **Evidence:** App allows configured origins plus localhost and regex `https?://.*\.onrender\.com`, with credentials and all methods/headers enabled.
- **Why it matters:** Any matching hosted origin can make credentialed browser requests. Direct non-browser API calls remain possible because authentication is absent.
- **Recommended fix:** Use only exact production frontend origins and disable credentials unless an intentional cookie-based auth flow needs them.
- **Acceptance criteria:** Production CORS tests allow only exact approved origins; unauthorized direct API calls remain blocked independently of CORS.

### SEC-06 — Dependency exposure is partly known, partly unassessed

- **Severity:** **Medium** audit gap; npm issues are **Moderate**, all transitive development dependencies.
- **Affected files/modules:** [frontend/package-lock.json](./frontend/package-lock.json), [backend/requirements.txt](./backend/requirements.txt), [backend/pyproject.toml](./backend/pyproject.toml).
- **Evidence:** Full `npm audit` reported 7 moderate transitive findings through `@typescript-eslint` / `minimatch`, including GHSA-g3hv-75wg-m249 (minimatch globparts amplification). `npm audit --omit=dev` reported zero production findings. Python `pip-audit` was unavailable; Python advisory status is **NOT VERIFIED**.
- **Why it matters:** The frontend development toolchain contains known advisory versions; backend dependency risk has not been assessed.
- **Recommended fix:** Do not auto-upgrade in this audit. After approval, resolve frontend dev-tool advisories in a separate task and run a Python scanner against the resolved deployment environment.
- **Acceptance criteria:** CI records reproducible audits for frontend and backend resolved dependencies; no unresolved high/critical advisories; remaining moderate findings have an owner and rationale.

### SEC-07 — Secret exposure scan not performed

- **Severity:** **Low** audit gap; no credential is disclosed here.
- **Affected files/modules:** Tracked source/configuration and repository history.
- **Evidence:** Example environment files were inspected; a full secret scanner/history scan was not run. `.env` files are ignored by [`.gitignore`](./.gitignore#L6), which does not establish that no secret was previously committed.
- **Why it matters:** A credential committed in history can remain usable even after removal from the current tree.
- **Recommended fix:** Run an approved local secret scan over tracked files and Git history; rotate any discovered credential. Do not copy secret values into reports.
- **Acceptance criteria:** Scanner result and reviewed exceptions are recorded; any exposed credential is revoked and removal/history remediation is verified.

## Controls reviewed

| Control | Finding |
|---|---|
| File extension | Upload accepts `.csv`, `.txt`, `.log`, `.pdf`; filename directory components are stripped. This is useful validation, not content safety or access control. |
| Upload bytes | Backend enforces a configured 1–1,024 MB limit; Render sets 25 MB. No uploaded-row cap exists. |
| PDF parsing | Signature, encryption, page count, extracted text size, and recognizable log-like content are checked; scanned PDFs are rejected. |
| SQL injection | Inspected SQLite queries use bound parameters; no direct SQL injection path identified in these code paths. |
| Path traversal | Filename is reduced to a basename and is not used as a storage path; no upload path traversal write was found. |
| XSS | React renders event values as text; no `dangerouslySetInnerHTML` use was found. This is not a full browser security test. |
| CSRF | No cookie/session auth is present, so cookie-based CSRF is not the current primary risk. Reassess if cookie auth is introduced. |
| CORS | Broad Render regex and `allow_credentials=True`; CORS does not protect direct API access. |
| Secrets | Comprehensive secret scan **NOT VERIFIED**; no secret values are reproduced. |
| Database | SQLite file contents are sensitive; no auth, tenant isolation, retention, or backup policy. |

## Required security gate

Before any public exposure: authenticate/authorize every log-bearing route; enforce tenant
isolation; bound upload rows, resource use, rate, and concurrency; safely serialize all
spreadsheet exports; define redaction/retention/deletion; use exact production CORS; scan
resolved frontend and Python dependencies; and test backup/restore and access controls.

**Verdict: NOT SAFE FOR PUBLIC/UNTRUSTED USE.** No vulnerability remediation or dependency
upgrade was performed.
