# TCT v1.11.7.1 — Prospective Permalink Quarantine Repair

## Production failure repaired

The first v1.11.7.0 production run correctly recovered trusted county coverage and completed the category-membership migration, but the final forward identity contract stopped deployment for two live vigil placements:

- `Community gathers to honor 9-year-old boy killed ...`
- `Community holds vigil for 9-year-old boy killed ...`

Both placements had been rebound to the historical permalink:

```text
2026-07-20-child-killed-another-injured-in-bicycle-crash-with-fedex-truck-in-fort-pierce
```

The gate reported `headline_slug_event_drift` and correctly failed closed.

## Root cause

The archive target was evaluated before mutation. At that point its stored `lastmod` was July 22, only two days after the July 20 slug date, so the legacy drift classifier still considered it live-safe. Updating the row on July 27 would advance `lastmod` to a seven-day gap and expose the substantial mismatch between the crash slug and the vigil headline.

The engine did not evaluate that prospective post-update state. It therefore wrote toward a target that only became quarantined during the later archive backfill.

## Repair

Before any existing archive row is updated, the engine now builds the row as it would exist after publication:

- incoming headline;
- incoming teaser/body excerpt;
- current-run `lastmod`;
- existing permanent slug and first-published identity.

If that prospective row would fail headline/slug alignment, the engine:

1. refuses the old update target;
2. marks the old row as a durable identity quarantine;
3. preserves the old HTML page and archive history;
4. removes stale live slug bindings from the current item;
5. creates a new permalink for the current article;
6. excludes the old row from canonical cleanup, recovery, ranking and live rebinding;
7. rebinds every current category clone with the same persistent story ID to the new safe permalink.

The quarantine is persistent. The normal post-write identity backfill cannot erase it merely because the unsafe incoming headline was never written to the old row.

## Defense in depth

The final forward live identity contract now re-evaluates headline/slug alignment directly in addition to checking persisted quarantine flags. The deployment gate remains unchanged in purpose and continues to fail closed if any unsafe URL reaches a live surface.

Forward identity diagnostics now include:

```json
{
  "quarantined_update_targets": [
    {
      "candidate_slug": "...",
      "reason": "prospective_headline_slug_event_drift",
      "action": "preserve_old_page_and_mint_new_permalink"
    }
  ]
}
```

## Safety boundary

Unchanged:

- trusted-source recovery;
- county membership projection;
- category filters and county panels;
- story relationships and follow-up activation;
- duplicate suppression;
- custom article authority;
- ranking mode;
- RSS GUID behavior;
- source-depth and nonstory gates.

## Validation

- Exact production vigil headline regressions: passed.
- Prospective same-headline/body-change drift regression: passed.
- Persistent quarantine backfill regression: passed.
- Canonical cleanup exclusion regression: passed.
- Two-category live rebind regression: passed.
- Focused forward identity suite: 16 passed.
- Workflow-equivalent suite: 354 passed.
- Package validation: 29 modules and 98 public exports.
- Existing warnings: 16 `datetime.utcnow()` deprecation warnings.
- No GitHub Actions or production workflow has run with v1.11.7.1.
