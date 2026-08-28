# v1.13.6.7r Review Guide — Shadow Source Integrity Authority

## Apply

Apply this overlay at repository root on top of the current v1.13.6.7q state.

## Test Editorial Engine expected result

- 1,018 tests
- 0 failures
- Package validation: 38 modules / 122 public exports

## Production / shadow validation

Run one normal Generate News cycle with the Assignment Editor Shadow enabled.

Review:

- `data/assignment-editor-shadow-report.json`
- `data/assignment-editor-shadow-review.md`
- `data/assignment-editor-shadow-answer-key.json`
- Generate News log

Expected new observability for each shadow category:

- `alignment_diagnostics.shadow.canonical_surface.blocked_source_integrity_rewrite_count`
- `alignment_diagnostics.shadow.canonical_surface.blocked_source_integrity_rewrites`
- `alignment_diagnostics.shadow.final_source_mapping.source_mapping_valid`
- `comparison_signals.challenger_final_source_mapping`

Acceptance rules:

1. A shadow source must never turn into a different event while retaining its source index.
2. Canonical rebound is allowed only by exact source provenance or explicit publication authority.
3. If final mapping cannot be proven, the category is unscoreable rather than silently scored.
4. The live publisher remains unchanged by this experiment.

## Bakeoff continuation

If the next shadow run is clean, resume scoring the Sonnet 5 assignment-editor + Sonnet 4.5 writer architecture. Do not count the contaminated St. Lucie comparison from the prior run as a Sonnet 5 loss; it was a deterministic alignment failure.
