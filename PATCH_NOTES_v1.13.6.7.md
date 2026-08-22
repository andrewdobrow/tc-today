# v1.13.6.7 — Material Update Promotion Integrity

## Why this increment exists

TCT already had two strong systems that were supposed to work together:

1. persistent-story duplicate suppression, which prevents a second URL for the same story; and
2. semantic material-update routing, which can refresh an existing canonical article in place when a later source materially advances that story.

Production showed an ordering defect between them. A source already recognized as the same persistent story could receive an editorial route of `skip` and be removed by the published-story guard **before** story-aware update context and semantic materiality were allowed to evaluate it. That made the duplicate guard capable of vetoing the update system.

The aligned assignment-editor experiment exposed two concrete forms of the failure:

- a later Vero Beach homicide source with body-camera arrest footage / extradition development could be treated only as an already-published same story; and
- the Palm City animal-hoarding story's later legal surrender of 36 Border Collies and Sept. 1 adoption process could be suppressed against the existing authoritative custom canonical instead of refreshing that canonical.

This is a core editorial-engine correction, not a model-bakeoff feature.

## Production behavior change

Before an already-published `skip` candidate is suppressed, TCT now gives a **narrow class of candidates** one materiality decision:

- deterministic persistent-story identity must already resolve the incoming source to one published canonical;
- the incoming item must be source-backed and publishable;
- the incoming source must be newer than the canonical's latest meaningful timestamp;
- an already-absorbed material-update source is never adjudicated again;
- the semantic decision may only authorize an in-place update to the already-proven canonical;
- `new_story` contradicting the proven identity fails closed to HOLD and can never mint another URL;
- model unavailability, validation failure, ambiguity, or the per-run materiality-call budget also fail closed to preserving the existing canonical.

A validated material update is promoted from `skip` to `update_existing` **before** the duplicate-suppression pass. TCT then attaches the existing canonical context and uses the normal update-lead, article-framing, publication-identity, permalink and canonical-write barriers.

## Authoritative custom canonicals

The existing custom-article protection remains the default: feed stories cannot overwrite hand-written authoritative custom articles and cannot mint a parallel feed URL.

There is one tightly bounded exception in v1.13.6.7: if deterministic identity already binds the source to that exact custom canonical **and** the pre-generation semantic materiality gate validates a genuine new development, TCT may refresh the custom canonical **in place**. The original custom slug, publication identity, custom flags and canonical authority are retained.

The incoming feed URL is appended to `source_history` with role `material_update`. No second article page is created.

## Safety / boundedness

- Default pre-generation materiality model-call budget: **12 per run** (`TCT_PREGEN_MATERIAL_UPDATE_MAX_MODEL_CALLS`).
- Only newer, source-backed, already-proven same-story candidates qualify.
- Older/equal sources spend zero materiality calls.
- Previously absorbed source URLs spend zero materiality calls.
- Semantic duplicate decisions remain suppressed exactly as before.
- Semantic HOLD/error/unavailable outcomes preserve the existing canonical and do not create a new URL.
- Existing contextual-update lead and universal article-framing contracts remain mandatory after promotion.
- Existing canonical-write authorization remains mandatory.
- Models used by normal category writing/selection are unchanged.
- No workflow, membership, routing-eligibility, archive data, registry data or publication content is shipped in this overlay.

## Observability

`data/category-generation-report.json` schema is bumped from **6 → 7** and now reports:

- `material_update_promotion_evaluation_count`
- `material_update_promotion_count`
- `material_update_promotion_cache_hit_count`
- `material_update_promotion_model_call_count`
- per-category `material_update_promotion_decisions`

`data/semantic-publication-gate.json` schema is bumped from **3 → 4** and now includes `pre_generation_materiality_decisions` plus summary counts for evaluations, promotions, duplicates, holds, model calls and cache hits.

`data/model-usage-report.json` classifies these calls separately as `material_update_decision`.

## Permanent production regressions

The regression suite now locks the following behaviors:

- **Waggle body-cam/extradition:** a newer source already proven to belong to the existing Vero Beach homicide story gets a materiality decision before `skip` suppression and can promote to `update_existing`.
- **Palm City Border Collies:** a validated legal-surrender/adoption development can refresh the exact authoritative custom canonical while preserving its slug and custom authority.
- **No-change same story:** a newer source judged semantically duplicate remains `skip` and is suppressed.
- **Older/equal same story:** no materiality model call is spent.
- **Destructive custom boundary:** the authorized Palm City update passes the real contextual-update contract, rewrites exactly one existing canonical article page, preserves the original slug/custom flags, records source history, remains live-bound to that canonical URL, and creates no duplicate article page.
- Material-update model usage receives its own telemetry workload class.
- Category and semantic report schema/counters are regression-covered.

## Validation

- Core material-update / identity / category focused suite: **142 passed** before final observability additions.
- Focused dedup + usage suite after final additions: **25 passed**.
- GitHub workflow-equivalent suite: **938 passed**.
- Warnings: **45**, consisting only of the existing `datetime.utcnow()` deprecation class. Two extra warning instances are exercised because the new destructive regression intentionally executes the archive writer.
- Package validation: **38 modules / 119 public exports**.
- Generator runtime hotfix guard: **PASS**.
- False-jurisdiction source guard: **PASS**.

## Production validation target

Run **Update Treasure Coast Today** with both model-experiment checkboxes off. A naturally recurring/new material same-story source should produce a log line beginning:

`Material-update promotion: kept ... newer same-story source(s) for canonical refresh before duplicate suppression`

For an authoritative custom canonical, a successful final write should also log:

`AUTHORIZED CUSTOM MATERIAL UPDATE: preserving custom canonical URL ... while applying verified new development`

The final proof is not merely that a model call occurred. The canonical URL must remain singular, the new development must be incorporated into that existing article, and the live placement must bind to that same canonical slug.
