# v1.13.6.5c Production Review Guide

Run **Update Treasure Coast Today** normally. Leave the Sonnet 5 shadow bake-off disabled for this validation run.

## Primary verification

Inspect `data/model-usage-report.json` after the run.

If the semantic publication gate is exercised, confirm:

- there is no `TypeError` failure from `semantic_publication_gate.py:adjudicate_candidates`;
- successful semantic adjudication is recorded under workload class `identity_decision` with usage metadata;
- no unsupported `temperature` request argument appears in the two semantic request sites.

If no semantic candidate requires a model call on that run, absence of an `identity_decision` request is valid; retain the hotfix and verify on the next naturally exercised run rather than manufacturing publication state.

## Safety checks

Confirm the usual production gates remain green, especially story regression, persistent identity integrity, forward live identity, canonical surface, and presentation contracts.

This release makes no model-selection, prompt, ranking, category-routing, article-writing, or publication-policy change.
