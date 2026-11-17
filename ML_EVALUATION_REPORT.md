# Machine-Learning Evaluation Report

**Audit date:** 2026-11-17  
**Evaluation data:** Checked-in public LogHub BGL 2k structured CSV  
**Conclusion:** ML components exist, but **generalization and production accuracy are NOT
ESTABLISHED**.

## What was evaluated

The current upload parser and `analyze_batch` pipeline were run against
[BGL_2k.log_structured.csv](./loghub/BGL/BGL_2k.log_structured.csv). The accompanying
[BGL README](./loghub/BGL/README.md#L1) documents `-` as a non-alert and other category tags
as alert labels. No synthetic data or random simulation labels were used as evaluation
evidence.

The sample contains **2,000 records**, **1,857 non-alerts**, **143 alert-category rows**, and
**120 distinct templates**. For this exploratory calculation, label truth was mapped as
`Label == "-"` → negative; any documented alert category → positive. The mapping is specific
to this dataset and is not a universal label rule.

Configuration: automatic detector selection, contamination `0.1`, grouping window 5 minutes.
With 2,000 rows and 120 templates, the current selector chose Isolation Forest.

## Measured output — in-sample only

The pipeline fitted TF-IDF and Isolation Forest on the full sample, then compared flags on
those same records. This is **not a held-out test** and cannot establish expected performance
on future logs.

| Metric | Measured value |
|---|---:|
| True positives | 22 |
| False positives | 190 |
| True negatives | 1,667 |
| False negatives | 121 |
| Precision | **0.1038** |
| Recall | **0.1538** |
| F1 | **0.1239** |
| False-positive rate | **0.1023** |
| False-negative rate | **0.8462** |
| Flagged events | 212 / 2,000 (**10.6%**) |

The flagged fraction is not exactly the configured 10%; score ties at the quantile threshold
can include multiple records. The current UI discloses this behavior.

### Timing and repeatability

- One local run measured **1.713 seconds** for file parsing + analysis + grouping, or about
  **1,167 events/second** for this one 2,000-row sample.
- Prediction flags were identical in a repeated local run with the same input and settings.
- Timing does not include persistence, HTTP transfer, export, browser rendering, or
  concurrency. It is not a production benchmark.
- Memory, CPU utilization, large files, concurrent uploads, and target deployment hardware
  were not measured.

## Parsing and field quality observed in that real upload

The API upload itself succeeded (HTTP 200), persisted the 2,000 events to an isolated
temporary SQLite database, and returned HTTP 200 for history/detail, PDF, and XLSX. Parsing
the fields showed:

| Field | Result |
|---|---:|
| Parsed records | 2,000 |
| Alert labels retained | 143 |
| Severity values missing | 0 |
| Normalized timestamps missing | **2,000** |
| Host values missing | **2,000** |
| Service values missing | **2,000** |
| Timestamp parser warning | Emitted; pandas fell back to per-element dateutil parsing |

The CSV has multiple timestamp-like columns and `Node`/`Component`. Current alias mapping
overwrites earlier matches in column order; `Node` is not a host alias and `Component` maps
to `source`, not `service`. The timestamp failure makes the result unsuitable for evaluating
time-based grouping. The detector scores message templates, so the timestamp/host parsing
failure does not repair or explain the low classification metrics.

The grouping pass flagged 212 rows but produced 20 groups, one per flagged template in this
sample; the largest group contained 51 rows. Since the keys and timestamps were missing,
grouping fell back to template-only matching and could combine events across nodes and
times. This is evidence of a data/correlation defect, **not an alert-reduction success
metric**.

## Pipeline implementation review

### Feature extraction and scoring

- [normalize_events](./backend/src/log_anomaly/preprocessing/normalize.py#L16) preserves
  `message`, derives a masked template, and normalizes timestamps. The template masks
  IPv4-like strings, UUIDs, long hex strings, and long numbers only.
- [analyze_events](./backend/src/log_anomaly/detection/analyze.py#L14) fits a new
  `TfidfVectorizer` on each upload. The vocabulary and scaling are file-relative; there is no
  stable cross-batch feature space.
- Isolation Forest uses `n_estimators=100`, `random_state=42`, and `n_jobs=1`; it fits and
  scores the same batch. The negative `decision_function` is min-max scaled within that
  batch, so scores are not calibrated probabilities and should not be compared across files.
- The final flag is a per-file quantile threshold. Equal scores can change the number
  flagged; `contamination` is not an empirically measured false-positive rate.
- Automatic mode chooses the baseline for fewer than 20 events or fewer than five distinct
  templates; otherwise it selects Isolation Forest. DBSCAN clustering is also run for
  metadata regardless of the selected scoring mode, adding work.

### Training, model loading, and versioning

- The API does **not** load the notebook's `log_anomaly_isolation_forest.joblib`; it fits
  per-upload models. The artifact is ignored by Git and is not a deployment contract.
- No model registry, model identifier, persisted vectorizer, feature-schema version,
  rollback, or training/inference compatibility check exists.
- There is no independent unseen-data inference protocol. Future unseen patterns are not
  tested against a stable trained vocabulary/model.
- Fixed `random_state=42` and identical repeated predictions support repeatability for this
  one local setup; they do not prove cross-version, cross-platform, or lifecycle
  reproducibility.

### Labels, severity, and false-positive handling

- The parser maps label-like CSV columns to `label`, but `/api/visualization/metrics` looks
  only for `ground_truth` ([visualization.py](./backend/src/log_anomaly/api/visualization.py#L62)).
- Dashboard label handling recognizes a limited binary vocabulary; BGL alert category
  strings are not mapped there. The reported BGL metrics above used the explicit BGL README
  mapping outside that UI.
- YAML score thresholds and `assess_severity` exist, but
  [analyze_batch](./backend/src/log_anomaly/service.py#L11) never calls that function.
  Source severity is not equivalent to a detector-derived incident severity.
- No analyst feedback, allowlist, suppression rule, cost-sensitive threshold calibration,
  or false-negative escalation mechanism was found.

## Findings

### ML-01 — No independent benchmark

- **Severity:** High.
- **Affected files/modules:** [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L156).
- **Evidence:** The uploaded records are used to fit and score the vectorizer/detector; current BGL same-file result has F1 0.1239 and recall 0.1538.
- **Why it matters:** In-sample metrics do not estimate future-source or future-time behavior; the false-negative count is high in this sample.
- **Recommended fix:** Establish a documented, time- or source-separated holdout, predeclare label mapping and threshold selection, and report baseline comparisons.
- **Acceptance criteria:** A clean rerun reproduces confusion matrix, precision/recall/F1, FPR/FNR, and uncertainty/limitations on a held-out labeled dataset.

### ML-02 — BGL field and label contract is inconsistent

- **Severity:** High for grouping/timelines; Medium for metric display.
- **Affected files/modules:** [parser.py](./backend/src/log_anomaly/ingestion/parser.py#L258), [normalize.py](./backend/src/log_anomaly/preprocessing/normalize.py#L27), [visualization.py](./backend/src/log_anomaly/api/visualization.py#L62).
- **Evidence:** All BGL timestamps, host, and service were missing after parsing; BGL label category strings are not a canonical binary field used consistently by every metrics path.
- **Why it matters:** Temporal correlation is invalid and evaluation display can silently disappear or disagree across API/UI.
- **Recommended fix:** Add an explicit BGL adapter, deterministic timestamp parsing, host/service mapping, and one canonical label schema.
- **Acceptance criteria:** Fixture tests cover all 2,000 rows with correct timestamps/identity/labels; API and UI return the same documented metrics inputs.

### ML-03 — Model artifact is not an inference artifact for the API

- **Severity:** Medium for current per-upload MVP; High if product claims trained-model serving.
- **Affected files/modules:** [analyze.py](./backend/src/log_anomaly/detection/analyze.py#L63), [backend/README.md](./backend/README.md#L20).
- **Evidence:** API fits per upload and never loads the notebook joblib artifact.
- **Why it matters:** Users may believe a deployed trained model is being applied when the service instead learns from each uploaded batch.
- **Recommended fix:** Explicitly choose per-file novelty scoring or implement a versioned train/serve lifecycle.
- **Acceptance criteria:** API response and UI identify the actual mode; trained inference tests load the expected artifact/version and exercise unseen logs, or documentation disclaims trained-model serving.

### ML-04 — Severity and false-positive workflow are not implemented end-to-end

- **Severity:** Medium.
- **Affected files/modules:** [service.py](./backend/src/log_anomaly/service.py#L11), [assess.py](./backend/src/log_anomaly/severity/assess.py#L13), [dashboard.tsx](./frontend/src/components/dashboard.tsx#L627).
- **Evidence:** Severity assessor is not called by the analysis flow; the UI has no analyst feedback/allowlist and calls non-alert rows “CLEAN.”
- **Why it matters:** Source log level, anomaly score, and incident severity are conflated; false positives are not operationally triaged.
- **Recommended fix:** Separate source severity from derived risk and add a documented analyst review/feedback policy.
- **Acceptance criteria:** Tests cover severity precedence/thresholds and feedback/suppression behavior; UI labels predictions as “not flagged,” not ground-truth clean.

## What cannot be concluded

- **Accuracy/generalization:** Cannot be established from the same-file BGL run.
- **HDFS performance:** The included HDFS sample has no event ground-truth labels; no accuracy claim is possible.
- **Other datasets/formats:** No independent labeled evaluation was run.
- **Production false-positive rate:** Not established by contamination or in-sample flags.
- **Production latency/throughput/capacity:** Not established by one local 2,000-row timing.
- **Synthetic simulation:** The simulation endpoint creates random ground-truth labels and was not used as evidence.

## Recommended evaluation acceptance gate

1. Select a documented, permitted, genuinely labeled public dataset and record version,
   provenance, label semantics, and parser version.
2. Use a held-out time/source split; fit preprocessing only on the training partition.
3. Report confusion matrix, precision, recall, F1, FPR, FNR, PR-AUC where valid, class
   prevalence, threshold policy, and confidence/limitations.
4. Compare against a frequency baseline and document label mapping and false-positive
   review costs.
5. Measure parse-to-result and end-to-end API latency, memory, CPU, throughput, and
   concurrency on the target runtime/hardware.
6. Do not claim production accuracy until independent runs reproduce the results.

**Conclusion:** TF-IDF and Isolation Forest are implemented, but production detection
quality is **NOT VERIFIED**. The only real labeled result in this audit is a weak,
non-independent exploratory calculation and must not be presented as a generalization
benchmark.
