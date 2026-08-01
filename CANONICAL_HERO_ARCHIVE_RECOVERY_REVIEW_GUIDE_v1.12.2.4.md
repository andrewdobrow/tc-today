# Canonical Hero Archive Recovery Review Guide — v1.12.2.4

## Production expectation

After category canonicalization, the final hero freshness barrier must complete without selecting a stale hero while a fresh canonical placement exists.

When no fresh live placement exists but a recent verified archive-recovery placement does, the log should include:

`Hero pre-filter: no fresh live candidates; using fresh canonical archive recovery`

followed by a successful canonical freshness contract.

## Reports to inspect

- `data/canonical-hero-freshness-contract.json`: `passed` must be true, with a fresh `after` selection.
- `data/front-page-hero-audit.json`: selection reason should be `deterministic_post_canonical_archive_recovery` when this recovery path is used.
- `data/semantic-publication-gate.json`: prior duplicate decisions and registry consolidation must remain intact.
- `data/story-regression-report.json`: production gate must pass.

## Regression boundary

A fresh archive-recovery candidate may beat stale live placements, but it must never displace an eligible fresh live candidate. Routine sports recovery remains subordinate to any fresh non-sports candidate.
