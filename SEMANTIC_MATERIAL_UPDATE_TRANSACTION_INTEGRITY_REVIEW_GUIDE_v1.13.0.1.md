# Review Guide — v1.13.0.1 Semantic Material Update Transaction Integrity

## Expected workflow behavior

For the Martin County shark-fishing update, the workflow should show one successful canonical refresh and then suppress any later same-source replay:

```text
SEMANTIC MATERIAL UPDATE: refreshed '<canonical-slug>' and redirected '<incoming-slug>'
SEMANTIC UPDATE REPLAY LOCK: preserved '<canonical-slug>' for already-absorbed source '<headline>'
```

The summary should report one applied material update, one update redirect, and at least one suppressed replay when the same source is still present in current category placements. It should not report a second material-update composition hold for that source.

## Registry checks

Review `data/semantic-publication-gate.json`:

- `summary.material_updates_applied` includes the successful update.
- `summary.material_update_replays_suppressed` increments when the same source reappears.
- A material-update registry directive exists only when `material_updates[]` contains the completed publication action.
- If consolidation would contaminate the canonical story, `registry_consolidation.skipped[]` contains `reason_code: merge_would_contaminate_target` and the relevant quarantine reasons.

Review `data/persistent-story-identity-integrity.json`:

- `passed` is `true`.
- `active_contaminated_count` is zero.
- `story_001155` is not listed under `active_contaminated_stories`.

A deferred registry merge is preferable to an invalid merge. The canonical article update and redirect may remain live while the internal fragment stays separate pending a targeted registry repair.

## Transaction test

A page-render or file-write failure must preserve both archive rows, preserve the original canonical metadata, create no redirect, and increment the material-update hold count. No partial canonical archive mutation is allowed.
