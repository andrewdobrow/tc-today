# v1.11.7.1 Production Review Guide

## Expected successful-run signals

The next production run should no longer end with the two vigil `headline_slug_event_drift` failures.

When the historical crash permalink is encountered as an update target, the log should contain a line similar to:

```text
FORWARD IDENTITY QUARANTINE: refused target '2026-07-20-child-killed-...' ... (prospective_headline_slug_event_drift)
```

The run should then:

- archive a new vigil permalink;
- preserve the old crash article file;
- rebind the Crime and St. Lucie placements to the same new canonical permalink;
- pass `Forward live identity contract`;
- pass `Live permalink integrity`;
- continue through homepage rendering and deployment.

## Reports to inspect

### `data/forward-publication-identity.json`

Confirm:

- `target_conflicts` contains the refused historical slug;
- `quarantined_update_targets` records `preserve_old_page_and_mint_new_permalink`;
- the new article is counted under `new_articles_stamped`.

### `data/archive-identity-backfill.json`

Confirm the old crash slug remains in `quarantined_records` with:

```text
prospective_headline_slug_event_drift
```

### `data/forward-live-identity-contract.json`

Expected:

```json
{
  "status": "passed",
  "violation_count": 0
}
```

### `archive.json`

Confirm:

- the old crash slug remains quarantined and excluded from live recovery;
- the current vigil article has a new slug aligned with its headline;
- both records may retain the same persistent story ID without the old row becoming canonical.

## Regression conditions

Stop and report the run if:

- either vigil headline still points to the July 20 crash slug;
- the old quarantine disappears after archive backfill;
- the new vigil slug is redirected back to the old crash slug;
- Crime and St. Lucie receive different permalinks for the same current vigil article;
- the final forward identity or permalink contract fails.
