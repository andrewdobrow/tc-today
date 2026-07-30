# TCT v1.12.0.3 — Authoritative Custom Archive Identity Backfill

## Production failure repaired

The July 30 production run completed story consolidation and archived the new summer reading product guide, but the final forward-live identity gate stopped deployment because an older authoritative custom article had no `editorial_story_id`.

The affected article was the July 20 Stuart animal-hoarding report. It already carried durable editor-owned identity (`custom_event_key` and `custom_fingerprint`) but predated the requirement that every live publication retain a persistent story ID.

## Fix

Historical authoritative custom archive records now receive a deterministic, publication-specific `custom:` story ID when one is missing.

The ID is derived only from stored custom/publication identity fields and the canonical slug. It never uses fuzzy headline similarity. Including the slug keeps recurring custom editions separate.

Backfilled records are stamped with:

- `editorial_story_id`
- `identity_origin: authoritative_custom_archive_backfill`
- `legacy_identity_status: identified`
- `ranking_eligible: true`

The existing forward-live identity contract remains fail-closed. No exemption was added.

## Scope

This release changes archive identity migration and release metadata only. It does not alter story matching, canonical redirects, update policy, product-guide rendering, Latest News chronology, or category ranking.
