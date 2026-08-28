# TCT v1.13.6.7r — Shadow Source Integrity Authority

## Why this increment exists

The 2026-08-27 assignment-editor bakeoff exposed a final-pipeline alignment defect in the publication-isolated shadow. A correctly assigned St. Lucie source (#2, the Port St. Lucie tornado corgi reunion) was written correctly by the Sonnet 4.5 writer, then final canonical-surface alignment trusted a contaminated persistent story identity and replaced the card with an unrelated July Orbeez/citizen-arrest canonical while preserving `source_index: 2`.

Because the numeric source index survived, the old report still marked `challenger_source_mapping_valid: true`. This could contaminate blind bakeoff scoring even though live publication was unaffected.

## Changes

- Adds immutable assignment provenance to every shadow-written placement:
  - `_assignment_source_index`
  - `_assignment_source_url`
  - `_assignment_source_title`
- Carries explicit canonical authorization from:
  - pre-generation canonical context; or
  - terminal permalink authority.
- Final shadow canonical-surface rebinding is now guarded:
  - canonical copy adoption is allowed when the canonical archive row has exact assigned-source provenance; or
  - live publication authority explicitly bound that assigned source to the canonical slug; or
  - the placement is deterministic fallback copy outside the source packet.
- A contaminated story ID / incident identity can no longer silently replace a shadow source with an unrelated archive story.
- Unsafe canonical rebounds are blocked and reported as `blocked_source_integrity_rewrites`.
- After every deterministic shadow correction, exact source mapping is recomputed in `final_source_mapping`.
- A surviving source index no longer counts as proof by itself.
- If final source mapping is invalid for any reason, the category fails closed as `FinalSourceMappingError` and is not scoreable.
- Assignment-editor artifact schema advances from 2 to 3 and experiment version advances to `1.13.6.7r`.
- `comparison_signals.challenger_source_mapping_valid` now comes from final-pipeline source validation, not the pre-write assignment plan.

## Permanent regressions

1. Exact 2026-08-27 corgi -> Orbeez contamination: a persistent story ID that points at the unrelated Orbeez canonical must not rewrite the corgi source.
2. Exact assigned-source provenance still permits a legitimate canonical rebound.
3. Final mapping rejects an unrelated story even when the original numeric `source_index` survives.
4. Bakeoff artifacts report final mapping validity and mark invalid categories unscoreable.

## Validation

- Package validation: 38 modules imported / 122 public exports verified.
- Focused shadow/canonical authority suites: 58 passed.
- Full editorial test gate: 1,018 passed / 0 failed.
- Existing warnings only: 41 `datetime.utcnow()` deprecation warnings.
