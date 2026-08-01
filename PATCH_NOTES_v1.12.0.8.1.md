# v1.12.0.8.1 — Quarantined Story ID Re-entry Barrier

## Problem

v1.12.0.8 correctly quarantined contaminated persistent stories and failed closed when a published archive row referenced one. A production run then exposed a remaining re-entry path: persisted editorial audit state could still remember an older source-to-story assignment after that story had been quarantined by registry repair.

The stale decision could be copied onto a current feed item, survive model generation, and reach the archive writer. The final persistent-story identity gate detected the reference and stopped deployment, but the invalid story ID should have been rejected before generation.

## Changes

- Load the registry quarantine set once at the start of every production run.
- Reject quarantined story IDs when current editorial decisions are remembered.
- Reset rejected decisions to `generate_new` / `new_story` so the current registry pass can resolve a fresh identity.
- Refuse quarantined IDs when an audited source decision is reused elsewhere in the same run.
- Refuse quarantined IDs when current-run story IDs are stamped onto cached or generated category copy.
- Strip all prior-run canonical authorization, cross-source match, update-context, and canonical-slug metadata from cached generated copy before current-run identity is applied.
- Run quarantine revocation again at the final archive write barrier, after all new rows have been appended.
- Allow exact-source identity backfill to attach a fresh safe story ID after that final revocation.
- Include the first concrete violation identifier in persistent-story integrity exceptions.
- Upload the key generation diagnostics as a GitHub Actions artifact even when generation fails.

## Production expectation

`data/persistent-story-identity-integrity.json` must report:

- `passed: true`
- `archive_quarantine_reference_count: 0`
- `violation_count: 0`

The workflow log should also show the number of quarantined story IDs loaded into the current-run denylist. A nonzero denylist count is normal; a final archive reference to one of those IDs is not.
