# v1.13.6.6a Assignment Editor Final-Pipeline Alignment — Review Guide

## Run

Open **Update Treasure Coast Today → Run workflow**.

- Leave **Run Sonnet 5 shadow model bake-off** unchecked.
- Check **Run Sonnet 5 assignment editor + Sonnet 4.5 writer shadow**.
- Run the normal production workflow.

The production publisher remains unchanged.

## Expected Generate News log

Near the end of Generate News, after the normal production timing, expect a line similar to:

```text
Assignment-editor shadow: N live-generated category packet(s) queued; editor=claude-sonnet-5; writer=claude-sonnet-4-5; comparison=final-pipeline-aligned
```

Each completed category reports editor/writer duration and its **final aligned shadow hero**. The completion line must include `final-pipeline alignment applied`.

## Blind review

Open `assignment-editor-shadow-review.md` first.

The heading must say **Final-Pipeline Blind Review** and the introduction must state that both displayed variants are final-pipeline comparison projections.

Do not open the answer key until A/B/Tie scores are recorded.

## Machine-report integrity checks

In `assignment-editor-shadow-report.json`:

- `schema_version` must be `2`;
- `experiment_version` must be `1.13.6.6a`;
- `comparison_stage` must be `final_pipeline_aligned`;
- each scoreable category must contain all four objects:
  - `raw_baseline_output`
  - `final_baseline_output`
  - `raw_challenger_output`
  - `final_challenger_output`
- the backward-compatible `baseline_output` and `challenger_output` aliases must point to the **final aligned** variants;
- `alignment_diagnostics.production` must record whether the final live category was found and how many deterministic archive filler cards were omitted from the comparison;
- `alignment_diagnostics.shadow` must expose stale-hero swaps, quality rejections, published-story suppressions, county-authority rejections, canonical rewrites/dedup, and whether shared deterministic archive recovery was used.

Raw-vs-final hero/source changes are expected and are the reason this patch exists. The blind review must always display the final variants.

## Answer key

`assignment-editor-shadow-answer-key.json` must include:

```text
comparison_stage: final_pipeline_aligned
```

The model/path identity remains blinded in the review itself.

## Model usage

`model-usage-report.json` should continue to show separate:

- `assignment_editor_shadow` calls on Sonnet 5;
- `assignment_writer_shadow` calls on Sonnet 4.5;
- normal production calls on the existing production model.

The alignment pass itself is deterministic and adds no model calls.

## Files to send back

Upload:

- `assignment-editor-shadow-review.md`
- `assignment-editor-shadow-answer-key.json`
- `assignment-editor-shadow-report.json`
- `model-usage-report.json`
- Generate News log
