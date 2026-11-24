# Gap Analysis

The repository is a working local MVP, but not production-ready.

## P0 gaps

| Finding | Current state | Missing | Impact |
|---|---|---|---|
| Authentication | No auth dependencies | Identity, authorization, tenant isolation | Stored logs and workloads are exposed |
| Upload safety | Byte limit only | Row/token limits, rate/concurrency controls | CPU/RAM denial of service risk |
| Export safety | Direct CSV/XLSX values | Formula-neutralized serialization | Spreadsheet formula injection |
| Data privacy | Limited template masking | Raw-evidence policy, redaction, retention/deletion | Sensitive log retention |

## P1 gaps

| Finding | Current state | Missing | Impact |
|---|---|---|---|
| BGL/source fields | 2,000 rows parsed; timestamps/host/service lost | Dataset schema mapping and timestamp parsing | Incorrect timelines and correlation |
| Label contract | Parser uses `label`; metrics expect `ground_truth` | One canonical label schema/adapters | Inconsistent or missing metrics |
| ML contract | Per-upload fit and same-batch scoring | Independent holdout, model mode/version | Weak and non-generalizable evidence |
| Severity | YAML rules exist but pipeline does not call them | Source-vs-derived severity contract | Misleading severity behavior |

## P2/P3 gaps

- No migrations, indexes, pagination, retention or backup/recovery policy.
- No readiness, metrics, structured security logs or release rollback.
- No server-side search, real charts, alert acknowledgement/resolution or frontend tests.
- No dedicated JSON/JSONL, EVTX, Nginx, syslog or broad vendor format validation.

The existing [MISSING_FEATURES.md](./MISSING_FEATURES.md),
[SECURITY_AUDIT.md](./SECURITY_AUDIT.md),
[ML_EVALUATION_REPORT.md](./ML_EVALUATION_REPORT.md) and
[PROJECT_AUDIT.md](./PROJECT_AUDIT.md) contain the finding register and evidence.
