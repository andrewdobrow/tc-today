# TCT v1.13.6.5 Model Bake-Off Review Guide

## Run it once

1. Apply the v1.13.6.5 overlay.
2. Open **Actions → Update Treasure Coast Today → Run workflow**.
3. Check **Run Sonnet 5 shadow model bake-off**.
4. Run the workflow normally.

The checkbox defaults off on future runs. Do not change `MODEL_ARTICLES` or `MODEL_SELECTION`.

## What to download

At the end of the workflow, open the **Artifacts** section and download `tct-model-bakeoff-<run_id>`.

Review **`model-bakeoff-review.md` first**. Do not open the answer key yet.

The blind review changes which model is Variant A or Variant B by category so one letter cannot reveal the challenger across the document.

## How to score it

For each scoreable category, choose A, B, or Tie for:

- hero/story choice;
- headline accuracy and strength;
- lead and context;
- factual fidelity;
- completeness;
- unnecessary filler;
- overall publishability.

Pay particular attention to recurring TCT weaknesses: choosing the actual news rather than a colorful side detail, explaining context in the lead, preserving concrete names/numbers, avoiding generic filler, and not overstating what the source supports.

After scoring, open `model-bakeoff-answer-key.json` and tally wins by model.

Then send ChatGPT these four files:

- `model-bakeoff-review.md`
- `model-bakeoff-answer-key.json`
- `model-bakeoff-report.json`
- `model-usage-report.json`

We can calculate the observed quality win rate and the exact incremental token/cost difference before deciding whether to promote Sonnet 5.

## Important isolation behavior

The Sonnet 5 call occurs only after the normal site build completes. Challenger output never enters publication state, generation cache, `all_categories`, archive identity, article pages, RSS, or homepage selection. A challenger API failure is logged and the live publication result remains unchanged.

A category that is a generation-cache hit is not re-generated just to satisfy the experiment. This keeps the bake-off from changing live publication behavior merely to create an evaluation sample.
