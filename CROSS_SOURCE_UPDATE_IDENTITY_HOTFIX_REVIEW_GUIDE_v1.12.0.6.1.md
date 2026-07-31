# v1.12.0.6.1 Production Review Guide

## Required workflow outcome

The production workflow must finish successfully and should return toward the normal runtime range. A modest variance from feed or model latency is expected; the archive identity matcher should no longer add a large quadratic delay.

## Required reports

Review:

- `data/cross-source-update-identity.json`
- `data/canonical-publication-ledger.json`
- `data/forward-live-identity-contract.json`
- `data/forward-publication-identity.json`
- `data/story-regression-report.json`
- `data/editorial_observability.json`
- `data/category-generation-report.json`

## Release-specific checks

1. No match may connect the Vero Beach fentanyl sentencing story to `2026-07-09-second-decomposed-body-found-near-us-1-in-sebastian-days-after-first-discovery`.
2. `canonical-publication-ledger.json` should report a bounded `cross_source_candidate_pairs` value rather than evaluating all archive pairs.
3. The Orbeez canonical archive row must have a non-empty `editorial_story_id` if it is placed live.
4. `forward-live-identity-contract.json` must report `passed: true` with zero violations.
5. Separate I-95 crashes, separate wrongful-death lawsuits, and unrelated court stories must remain separate.
