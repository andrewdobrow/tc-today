# v1.13.1.1 — Registry Fixed-Point Preflight

## Purpose

Make persistent-story registry repair truly idempotent before validation and
publication. A later identity merge could expose a source-identity duplicate that
an earlier repair layer had already passed, leaving the tracked registry one merge
behind and causing the next workflow test to fail.

## Fixes

- Repeats exact, source, unified-incident and conservative incident identity layers
  until no additional story record can be removed.
- Adds a bounded, atomic registry preflight before package validation and pytest in
  both GitHub Actions workflows.
- Verifies a second in-memory repair pass is clean before persisting a changed
  registry.
- Preserves fail-closed behavior if repair cannot reach a fixed point.
- Adds regressions for late-emerging identity components, atomic preflight repair,
  and workflow ordering.

## Production case

The failed run found one remaining source-identity duplicate after the first repair:
`story_002256` still needed to merge into `story_002213`. The preflight now performs
that merge before the idempotence regression runs, and the repair engine prevents
the same one-pass lag from recurring.
