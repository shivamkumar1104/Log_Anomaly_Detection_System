# Improvement Roadmap

## Recommended top five

1. **Authentication and tenant isolation**
   - Best foundation for every log-bearing feature.
   - Solves the highest security risk.

2. **Upload, row and concurrency limits**
   - Protects availability and makes deployment sizing measurable.

3. **Safe CSV/XLSX exports**
   - Low-complexity, high-impact security fix.

4. **Privacy, redaction and retention**
   - Required before storing real organizational logs.

5. **BGL and label contract repair**
   - Repairs core evidence, timestamps, grouping and metric semantics.

## Sequence

1. Keep public deployment disabled.
2. Implement P0 trust boundaries and tests.
3. Repair source parsing, labels and severity contracts.
4. Build an independent benchmark and choose per-file versus versioned model inference.
5. Replace ad hoc SQLite lifecycle with migrations, pagination and retention.
6. Add alert workflow, search and tested frontend workflows.
7. Run deployment, load, backup/restore and rollback gates.

Avoid major framework, database or queue migrations until measured workload and identity
requirements justify them.
