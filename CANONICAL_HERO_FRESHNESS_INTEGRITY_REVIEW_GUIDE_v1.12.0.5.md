# Canonical Hero Freshness Integrity Review Guide — v1.12.0.5

Review `data/canonical-hero-freshness-contract.json` after production.

Required:

- `passed` is `true`.
- The final hero uses its canonical `first_published` timestamp unless `meaningful_update_validated` is true.
- `lastmod` never controls hero eligibility.
- A stale canonical hero is replaced whenever `fresh_candidate_count` is greater than zero.
- The July 20 Stuart hoarding article cannot receive July 30 freshness from repeated source coverage.
- A validated meaningful update may use `last_meaningful_update_at` only after the contextual update contract passes.

Expected production log:

`Canonical hero freshness contract PASSED`
