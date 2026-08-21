# TCT v1.13.6.3 — Model Usage & Cost Observability Review Guide

## Purpose

Measure the exact Anthropic workload and estimated standard/global list cost of a real **Update Treasure Coast Today** run before changing production models.

This release is observability-only. The production model remains `claude-sonnet-4-5` for both `MODEL_ARTICLES` and `MODEL_SELECTION`.

## Expected production output

At process exit, the generator prints a summary beginning with:

`Model usage:`

It includes request count, base input tokens, prompt-cache writes, prompt-cache reads, output tokens, and estimated list cost. It then prints one cost line per workload class.

A successful run also writes:

`data/model-usage-report.json`

## Important workload classes

- `mixed_generation_and_selection` — the large category-generation request that currently both selects stories and writes the hero/cards.
- `classification` — local/category classification.
- `editorial_selection` — front-page selection, ranking, and semantic duplicate-list selection helpers.
- `identity_decision` — model-assisted same-event/canonical adjudication.
- `update_decision` — semantic material-update adjudication.
- `writing_enrichment` — second-pass card/hero rewrites when deterministic publication quality is not already sufficient.
- `writing_rewrite` — focused alert-to-article rewriting.

## What to send back after the run

Either:

1. the production workflow log containing the `Model usage:` section, or
2. `data/model-usage-report.json` from the post-run repository.

The JSON report is preferred because it preserves call-level token counts and lets us price alternative model splits without guessing.

## Safety checks

The report must not contain prompts, article/source text, generated copy, API keys, or personal data. A telemetry exception must print an observability warning and must not change generator success/failure behavior.
