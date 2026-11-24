# Product Vision

**Anomaly Detect** should evolve from a local batch-analysis MVP into a reliable, explainable
Log Intelligence and AIOps platform.

## Users

- Developers investigating application failures.
- Operations teams triaging repeated or unusual logs.
- Security and reliability analysts reviewing evidence.

## Core promise

Ingest logs, preserve traceable evidence, detect unusual patterns, correlate repeated alerts,
and help analysts decide what to investigate next. An anomaly is a prediction, not a confirmed
incident or root cause.

## Product stages

1. **Reliable foundation:** correct parsing, bounded resources, safe storage and exports.
2. **Intelligent detection:** reproducible benchmarks, honest thresholds, explainable results.
3. **Log intelligence:** format adapters, search, correlation, alert lifecycle and feedback.
4. **Production operations:** identity, observability, backups, CI/CD and deployment recovery.

## Non-goals

- Replacing Grafana, Datadog or Splunk wholesale.
- Requiring deep learning or an LLM for core detection.
- Adding Kafka, Redis or PostgreSQL before workload evidence requires it.
- Calling model predictions confirmed incidents or ground truth.
