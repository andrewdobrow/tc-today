# v1.12.0.6.2 Production Review Guide

## Required workflow outcome

The production workflow must complete successfully without reintroducing the v1.12.0.6 quadratic runtime. The generator should remain near the normal runtime range, subject to feed and model latency.

## Required reports

Review:

- `data/cross-source-update-identity.json`
- `data/cross-source-identity-repair.json`
- `data/canonical-publication-ledger.json`
- `data/forward-live-identity-contract.json`
- `data/forward-publication-identity.json`
- `data/story-regression-report.json`
- `data/editorial_observability.json`
- `data/category-generation-report.json`

## Release-specific checks

1. No cross-source match may connect any fentanyl-sentencing article to the July 9 Sebastian deaths permalink.
2. No cross-source match may connect the Fort Pierce sexual-battery article to the Port St. Lucie roof-chase permalink.
3. No cross-source match may connect the West Palm Beach police-union article to the Worth Avenue parking-impersonation permalink.
4. `cross-source-identity-repair.json` should report `repaired_count: 2` on the first run after the affected production workflow, then `0` on later clean runs.
5. The July 9 permalink must again show the Indian River County Sheriff bad-drugs/deaths article.
6. The July 30 roof-chase permalink must again show the Port St. Lucie chase article.
7. The fentanyl-sentencing and Fort Pierce sexual-battery stories should either receive their own proper permalinks or remain unpublished for ordinary editorial reasons; they must never overwrite unrelated pages.
8. `forward-live-identity-contract.json` and `story-regression-report.json` must pass.
