# TCT v1.13.6.7 — Material Update Promotion Integrity Review Guide

## Purpose

Validate the core persistent-story contract:

> A later source about the same real-world story must not create a duplicate URL. If it contains a meaningful new development, TCT should refresh the existing canonical article in place instead of silently discarding the update.

This increment changes live editorial routing. It is independent of the Sonnet model bakeoff and assignment-editor shadow experiments.

## Run settings

Use the production workflow **Update Treasure Coast Today**.

For the first validation run:

- `Run Sonnet 5 shadow model bake-off`: **unchecked**
- `Run Sonnet 5 assignment editor + Sonnet 4.5 writer shadow`: **unchecked**

This keeps the run focused on live material-update routing.

## What to inspect

Primary artifacts:

1. Generate News console log
2. `data/category-generation-report.json`
3. `data/semantic-publication-gate.json`
4. `data/model-usage-report.json`
5. `archive.json` / the affected live article only when a promotion actually occurred

## Expected routing order

For an already-published persistent story:

1. deterministic story identity resolves one canonical;
2. if the source is newer and source-backed, pre-generation materiality is evaluated;
3. semantic duplicate/no-change → remain `skip` → normal published-story suppression;
4. validated material update → promote to `update_existing`;
5. attach original canonical context;
6. normal category generation writes the update;
7. contextual update-lead and article-framing contracts must pass;
8. target-bound canonical write authorization must pass;
9. rewrite the same canonical slug in place;
10. live placement points to that same canonical URL.

At no point may this path authorize a second permalink for the proven story.

## Key console signals

When at least one candidate is promoted, expect:

`Material-update promotion: kept N newer same-story source(s) for canonical refresh before duplicate suppression`

For a custom canonical that receives a validated material update, expect:

`AUTHORIZED CUSTOM MATERIAL UPDATE: preserving custom canonical URL '...' while applying verified new development`

A no-change source should still appear only in normal published-story suppression and should not create a new article.

## Category report — schema 7

Check `data/category-generation-report.json`:

- `schema_version` = `7`
- summary and per-category counts for:
  - `material_update_promotion_evaluation_count`
  - `material_update_promotion_count`
  - `material_update_promotion_cache_hit_count`
  - `material_update_promotion_model_call_count`
- inspect `material_update_promotion_decisions` for the affected category.

For a promotion, the decision row should identify the existing canonical slug and show `promoted: true` / action `update_existing_canonical`.

## Semantic publication report — schema 4

Check `data/semantic-publication-gate.json`:

- `schema_version` = `4`
- `pre_generation_materiality_decisions`
- summary fields:
  - `pre_generation_materiality_evaluations`
  - `pre_generation_materiality_promotions`
  - `pre_generation_materiality_duplicates`
  - `pre_generation_materiality_holds`
  - `pre_generation_materiality_model_calls`
  - `pre_generation_materiality_cache_hits`

A validated promotion should show the exact canonical slug selected, same-event true, material update true, and the model's bounded novel-fact evidence.

## Cost telemetry

If a live materiality call occurs, `data/model-usage-report.json` should include workload class:

`material_update_decision`

Older/equal or already-absorbed sources should not consume this model-call budget.

## Exact permanent regressions

The code package includes permanent tests for:

### Vero Beach homicide / Waggle

A canonical story already exists for the homicide/manhunt. A newer source adds body-camera footage of the arrest and extradition status. The source is not allowed to mint another URL, but it is allowed to prove materiality before duplicate suppression. A validated decision promotes it to `update_existing`.

### Palm City hoarding / 36 Border Collies

The authoritative custom canonical remains the only canonical URL. A newer source says the owner legally surrendered the 36 Border Collies, clearing the adoption path and establishing a Sept. 1 application date. A validated decision may refresh that exact custom canonical in place. The custom slug and authority flags remain unchanged and the incoming source is recorded as a material-update source.

### Negative controls

- newer but semantically unchanged source → suppressed;
- older/equal source → no model call;
- materiality model failure/ambiguity → preserve canonical, no duplicate;
- contradictory `new_story` answer after deterministic same-story proof → fail-closed HOLD, no duplicate.

## Pass criteria for production

A run is strong production validation when at least one natural material update is encountered and all of these are true:

- deterministic identity already pointed to one existing canonical;
- the pre-generation materiality layer promoted it;
- the update survived normal lead/framing/identity guards;
- the existing canonical page was updated;
- its original slug remained the canonical URL;
- no second article page was created;
- the live category placement resolves to that same slug;
- regression and final canonical contracts remain green.

If a run contains zero qualifying newer same-story sources, zero promotions is not itself a failure. Do not manufacture a production update merely to exercise the path; the permanent regressions cover the exact known failures until a natural source appears.
