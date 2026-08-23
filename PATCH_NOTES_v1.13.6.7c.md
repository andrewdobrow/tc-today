# v1.13.6.7c — Fragmented Identity Material-Update Promotion Integrity

## Why this increment exists

The August 22/23 production validation proved that v1.13.6.7 can refresh an existing canonical story in place: the Matthew Waggle body-camera development was absorbed into the existing August 20 canonical URL. The same run exposed a narrower ordering defect in the Palm City Border Collie story.

The incoming WPTV surrender/adoption source still carried fragmented registry story ID `story_003665`, while the published canonical story uses the authoritative custom ID `custom:887b7f68e86a4dd4d39e4aa93d4f0b89`. The stronger canonical publication ledger correctly recognized both records as the same incident through the structured incident identity `mass-animal-hoarding:martin-county`, but that reconciliation occurred after the pre-generation material-update promotion pass.

Result: a plausible material update could miss semantic materiality evaluation, become canonical-bound later, and then be removed by terminal published-story suppression.

## Changes

### 1. Pre-generation materiality promotion can use canonical publication identity

`_promote_published_skip_material_updates()` now accepts the already-built canonical publication ledger. If the incoming source is an editorial `skip` and the registry-story-ID lookup cannot find the published canonical, the function asks the stronger deterministic publication ledger for the canonical target **before** giving up on materiality evaluation.

This is an ordering correction. The ledger does not itself declare the source a material update; it only supplies the correct canonical comparison target.

### 2. Corrected canonical identity survives a no-update decision

When the publication identity authority has granted a target-bound canonical write authorization, `_published_skip_canonical()` can use that hard identity proof to corroborate the already-published canonical even if the incoming registry story ID was fragmented.

This is required for the negative path: if the semantic materiality gate determines there is no meaningful new development, the corrected source must still reach terminal duplicate suppression rather than escaping as a new story.

### 3. Existing pre-generation ledger is reused

The category pipeline passes the already-built pre-generation publication ledger into material-update promotion instead of rebuilding it for each category.

## What is intentionally unchanged

- No model selection or Sonnet prompt changes.
- No Hometown News policy changes; v1.13.6.7b remains intact.
- No broad duplicate-match threshold is loosened.
- No manual story-ID special case is added for Waggle or the Border Collies.
- Canonical identity still does **not** authorize an update by itself. Semantic materiality remains required.
- Canonical/permalink behavior is unchanged: a material update targets the existing canonical rather than minting a second URL.

## Permanent regressions

`tests/test_published_story_skip_dedup.py` now includes:

1. **Fragmented Border Collie identity + material development**
   - incoming registry ID: `story_003665`
   - canonical ID: authoritative custom story ID
   - shared structured incident identity: `mass-animal-hoarding:martin-county`
   - expected: ledger reconciliation occurs before materiality evaluation; material update is promoted against the existing canonical.

2. **Fragmented identity + no material development**
   - hard canonical identity is reconciled
   - semantic gate says duplicate/no meaningful update
   - expected: source remains suppressed; no automatic promotion and no duplicate URL.

## Validation

- Exact published-story/material-update regressions: **19 passed**.
- Assignment-editor shadow + Hometown retirement + published-story regressions: **37 passed**.
- Workflow-equivalent suite: **945 passed**, with the same **45 known `datetime.utcnow()` deprecation warnings**.
- Package validation: **38 modules / 119 public exports**.
- `scripts/generate.py` syntax compilation: **PASS**.
