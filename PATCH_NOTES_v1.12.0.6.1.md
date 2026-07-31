# Treasure Coast Today v1.12.0.6.1

## Cross-Source Update Identity Performance Hotfix

This hotfix corrects the failed v1.12.0.6 production run.

### Fixed

- Replaced the archive-wide cross-source identity scan with deterministic candidate blocking and reusable feature extraction.
- Prevented unrelated stories from matching solely because they share broad drug, crash, lawsuit, highway, court, or locality language.
- Prevented institutional names such as `Florida Supreme Court` from being treated as street-level locations.
- Backfilled a proven legacy canonical archive row with the current persistent story ID before a no-rewrite ledger preservation, preventing `forward_published_article_missing_story_id` at the final live identity gate.
- Added regressions for the false Vero Beach fentanyl match, separate I-95 crashes, separate wrongful-death cases, bounded candidate evaluation, and legacy canonical story-ID adoption.

### Runtime impact

On the uploaded 635-record archive, candidate blocking reduced historical pair evaluation from 201,295 possible pairs to approximately 1,437 candidates. The local archive reconciliation benchmark completed in about 1.7 seconds.

### Production expectations

- The unrelated fentanyl sentencing article must not bind to the July 9 Sebastian bad-drugs/death article.
- The June 27 Orbeez canonical page may be preserved, but it must carry the current persistent story ID before final validation.
- `data/canonical-publication-ledger.json` includes `cross_source_candidate_pairs` for runtime review.
- `data/forward-live-identity-contract.json` must pass.
