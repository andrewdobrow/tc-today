# TCT v1.13.7.1g — Generated Material-Update Handoff Integrity Hotfix

## Production failure addressed

The Sept. 1 production run proved that discovery, editorial ranking, source depth, and semantic materiality were all working for the Michael Anthony Debevec body-recovery development, but the generated placement was still destroyed after article generation.

The run selected the body-recovery story as the live hero in both Crime & Safety and Martin County, stamped current-run forward identity, and then immediately logged `Published-story guard removed 1 generated placement(s)` in both categories. No article then reached archive publication (`Archived 0 new, updated 0 existing`).

## Root cause

`_suppress_published_skip_placements()` invokes the late material-update write barrier on a **generated article placement**, not the original RSS source row.

The original source row had already passed the pre-generation semantic material-update gate and received target-bound canonical write authorization. But the generated placement did not reliably carry all of the source-only evidence required by `_published_skip_material_update_candidate()` (notably verified source-depth provenance and publication time).

That created two bad paths:

1. A generated placement that already carried valid pre-generation material-update authority could be forced through a second eligibility check and lose the decision it had already earned.
2. A generated placement whose canonical relationship was resolved only after generation lacked enough source receipt data for the late barrier to evaluate materiality, so it failed closed as an ordinary published-story duplicate and was deleted.

In the Debevec case, the result was catastrophic: TCT generated the correct major update and then removed it before forward publication.

## Changes

### 1. Reuse target-bound pre-generation material-update authority

Added `_has_target_bound_pre_generation_material_update_authority()`.

When a generated placement already carries all of the following:

- `_semantic_material_update`
- `_pre_generation_material_update_promotion`
- the exact promoted canonical slug
- a valid target-bound canonical write authorization

…the late published-story barrier now reuses that validated decision directly. It does not require a second RSS timestamp, a second model call, or a second source-depth decision.

### 2. Preserve a verified source receipt on generated placements

`_stamp_current_run_story_ids()` now carries forward:

- `source_published`
- `_source_candidate_publishable_verified`

from the exact selected source row.

This gives genuinely late-resolved generated placements enough source provenance to receive a late materiality decision instead of being silently treated as no-change duplicates.

The receipt fields are cleared and recomputed on every stamp so cached placements cannot inherit stale source authority.

### 3. Late materiality accepts verified source-depth provenance

`_published_skip_material_update_candidate()` now accepts either:

- the original source row passing `_source_candidate_publishable()`, or
- a generated placement carrying `_source_candidate_publishable_verified` from its exact source row.

This preserves the source-depth safety contract while allowing the post-generation write barrier to operate on generated copy.

### 4. Shared authority helper

The pre-generation duplicate guard now uses the same target-bound authority predicate as the late barrier, reducing the chance that the two destructive gates drift apart again.

## Regression coverage

Added tests proving that:

- a target-bound pre-generation material update is reused even when the generated placement has no RSS timestamp;
- generated placements receive source publication time and verified source-depth provenance from their exact source row;
- a generated `skip` placement with a verified source receipt can receive late semantic materiality and survive suppression;
- a promoted generated placement targeting an authoritative custom canonical is not deleted by the post-generation published-story guard.

## Validation

- Focused published-story suppression suite: 29 passed.
- Missing-person + semantic material-update + final-publication + assignment-editor targeted suite: 117 passed.
- Exact Test Editorial Engine pytest command: **1074 passed, 0 failed**.
- `scripts/validate_package.py`: **passed** — 38 modules imported, 122 public exports verified.

## Expected production invariant

For the Debevec body-recovery source, a future run may legitimately choose to update the existing Aug. 29 canonical rather than create a second permalink. It must **not** log `Published-story guard removed 1 generated placement(s)` for the promoted body-recovery hero. A validated material update must survive into forward publication.
