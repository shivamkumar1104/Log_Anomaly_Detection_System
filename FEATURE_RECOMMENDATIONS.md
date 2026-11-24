# Feature Recommendations

## P0

1. **Authentication and tenant isolation**
   - Problem: Every log-bearing endpoint is publicly callable.
   - Priority: Critical. Complexity: High.
   - Recommendation: Implement first; keep public deployment disabled meanwhile.

2. **Upload limits and rate control**
   - Problem: Row count, concurrency and CPU cost are unbounded.
   - Priority: Critical. Complexity: Medium.
   - Recommendation: Define resource SLOs, then add rate/concurrency/row limits.

3. **Safe exports**
   - Problem: Formula-leading log values reach spreadsheets unchanged.
   - Priority: High. Complexity: Low.
   - Recommendation: Centralize safe CSV/XLSX serialization.

4. **Privacy and retention policy**
   - Problem: Raw messages persist indefinitely.
   - Priority: High. Complexity: Medium.
   - Recommendation: Redaction, deletion, retention and access policy.

## P1

5. **Structured CSV field mapping**
   - Problem: BGL timestamps, host and service are lost.
   - Benefit: Correct timeline, attribution and grouping.
   - Complexity: Medium.

6. **Canonical event and label schema**
   - Problem: Inconsistent truth and source fields.
   - Benefit: Valid metrics across UI, API and datasets.
   - Complexity: Medium.

7. **Independent ML benchmark**
   - Problem: Current BGL metrics are in-sample and weak.
   - Benefit: Honest detector quality evidence.
   - Complexity: Medium-High.

8. **Model contract decision**
   - Problem: API refits a detector per upload and ignores the notebook artifact.
   - Benefit: Clear, repeatable inference and lifecycle.
   - Complexity: Medium.

## P2/P3

9. **Database lifecycle and pagination**
10. **Alert acknowledgement, resolution and feedback**
11. **Server-side search and investigation charts**
12. **Format expansion and row-level parser traceability**

Only #1–#8 are release-critical or core-quality priorities. Format expansion should follow
verified source datasets rather than broad feature claims.
