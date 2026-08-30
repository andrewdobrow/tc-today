# TCT v1.13.7.0 — Homepage Editorial Ranking Authority, Shadow Phase

## Purpose

This increment starts the next product-quality phase after the v1.13.6.x integrity work. It upgrades the existing observe-only homepage ranking recommendation into an explicit editorial-deck shadow system. **It does not change the live homepage order or hero.**

## What changes

- Replaces the old persistent-score-only recommendation order with a guarded editorial score that independently considers:
  - persistent story importance,
  - canonical freshness,
  - live urgency,
  - Treasure Coast locality,
  - source trust,
  - breaking status,
  - validated material-update freshness.
- Applies the same basic freshness discipline as the live Top Stories surface:
  - normal stories must be within 48 hours,
  - high-urgency stories may survive to 60 hours,
  - transient alerts/closures expire after 24 hours,
  - routine sports stories expire after 24 hours unless exceptionally urgent.
- Routine `lastmod` edits do not make an old story fresh. A validated material update may refresh the canonical story.
- Adds soft category and single-county saturation penalties while deliberately **not** imposing county quotas.
- Custom/TCT-authored articles now compete normally in the shadow recommendation. They are not automatically position-locked. Explicit `pin_position` remains authoritative.
- Identity conflicts and non-high-confidence registry matches remain position-locked and continue to block enforcement readiness.
- Adds a guarded hero recommendation with an 8-point margin requirement. The recommendation is still observe-only.
- Produces both:
  - `data/homepage-ranking-recommendations.json`
  - `data/homepage-ranking-review.md`
- The Markdown review shows current vs. recommended hero/deck, scores, move explanations, and guardrails for manual editorial review.

## Important non-changes

- `card_reordering_enabled` remains `false`.
- `hero_changes_enabled` remains `false`.
- No permalink, story identity, source mapping, publication suppression, or canonical-routing authority is granted to the ranker.
- No new model call is added.
- The Sonnet 5 / Opus 5 assignment-editor bakeoff is unchanged.

## Production validation plan

Run this shadow for 3–5 normal Generate News cycles and review `data/homepage-ranking-review.md` after each run. Do not grant live authority until the recommendations are consistently preferable to the current homepage and identity/freshness readiness is clean.

## Validation

- Package validation: **38 modules / 122 public exports**
- CI-equivalent editorial suite: **1,042 passed / 0 failed**
- Existing warnings: **43 datetime deprecation warnings**
