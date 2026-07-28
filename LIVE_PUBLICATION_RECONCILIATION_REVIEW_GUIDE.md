# v1.11.7.4 Production Review Guide

After applying v1.11.7.4 over v1.11.7.3, run the normal production workflow.

## Expected log indicator

Look for:

```text
Live publication reconciliation: N rebound, N card(s) removed, N hero(s) recovered
Forward live identity contract PASSED
```

For the failed July 28 run, the expected behavior is that the Wells Fargo and Geoffrey Lang headline variants bind to their canonical same-run article pages rather than producing `archive_entry_missing` violations.

## Review file

Inspect:

```text
data/live-publication-reconciliation.json
```

Confirm:

- `protected_unresolved_count` is zero.
- Rebound rows point only to real archive slugs.
- Removed rows are thin or intentionally skipped non-custom placements.
- No custom article is removed.

## Existing reports to collect

- Complete workflow log
- `data/live-publication-reconciliation.json`
- `data/forward-live-identity-contract.json`
- `data/category-membership-report.json`
- `data/trusted-source-recovery.json`
- `data/editorial_observability.json`
- `data/story-regression-report.json`

Do not relax the final forward identity gate. A remaining protected unresolved publication should still fail the workflow.
