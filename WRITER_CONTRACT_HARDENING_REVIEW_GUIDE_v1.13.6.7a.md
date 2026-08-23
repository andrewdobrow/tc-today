# TCT v1.13.6.7a — Writer Contract Hardening Review Guide

## Purpose

Remove two sources of noise from the next final-pipeline-aligned assignment-editor comparison:

1. prompt drift between the live Sonnet 4.5 writer and the Sonnet 4.5 writer used behind the Sonnet 5 assignment editor; and
2. deterministic false rejection of valid fatal-shooting update leads that use normal words such as `killing` or `murdered`.

The deterministic money/headline contract stays strict.

## Required workflow

1. Apply this ZIP at repository root.
2. Run **Test Editorial Engine**.
3. If green, run **Update Treasure Coast Today** with:
   - `Run Sonnet 5 shadow model bake-off`: **unchecked**
   - `Run Sonnet 5 assignment editor + Sonnet 4.5 writer shadow`: **checked**
4. Upload the Generate News log plus:
   - `data/assignment-editor-shadow-review.md`
   - `data/assignment-editor-shadow-answer-key.json`
   - `data/assignment-editor-shadow-report.json`
   - `data/model-usage-report.json`
   - a fresh production repo ZIP.

## What to inspect

For the next aligned run, pay special attention to `alignment_diagnostics.shadow.quality_guard`.

Expected direction:

- a correctly contextualized fatal-shooting update should no longer be rejected merely because the first paragraph says `killing` rather than `killed`/`died`;
- a headline with a money claim must have the equivalent magnitude in paragraph one;
- `$22K` in the headline and `$22,000` in paragraph one should compare equal;
- if the amount remains only in paragraph two, `headline_money_claim_missing_from_lead` should still reject the item;
- no additional writer model call should be introduced by this increment.

## Promotion rule

Do not promote Sonnet 5 from one favorable run. Continue the final-pipeline-aligned experiment across multiple naturally generated categories/runs. The candidate architecture remains:

**Sonnet 5 assignment editor -> Sonnet 4.5 writer**

versus current production, both after the same deterministic finalization.
