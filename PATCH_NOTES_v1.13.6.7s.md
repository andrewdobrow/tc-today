# TCT v1.13.6.7s — Three-Way Assignment Editor Bakeoff

## Why this increment exists

The Sonnet 4.5 production path and Sonnet 5 assignment-editor shadow have now produced enough real runs to show that Sonnet 5 can improve abstention, recovery, supporting-story coverage, and some hero choices, but the difference is not consistently large. The next useful experiment is to test whether a stronger assignment editor produces a materially better newsroom slate.

This increment adds Claude Opus 5 as a second publication-isolated assignment-editor challenger while preserving production Sonnet 4.5 and the existing Sonnet 5 challenger.

## Experiment architecture

Every queued live-generated category packet now produces up to three final-pipeline comparison projections:

1. **Current production** — existing Sonnet 4.5 mixed generation/selection path, captured from the actual final live category.
2. **Sonnet 5 editor -> Sonnet 4.5 writer** — existing shadow architecture.
3. **Opus 5 editor -> Sonnet 4.5 writer** — new challenger architecture.

The Sonnet 5 and Opus 5 editors receive the same source packet, the same assignment prompt and assignment contract, and no publication-copy authority. Both use the same Sonnet 4.5 single-source writer and then pass through the same deterministic final-pipeline projection, terminal authority, canonical surface, and v1.13.6.7r final source-integrity validation.

The live publisher is unchanged.

## Changes

- Adds `TCT_ASSIGNMENT_EDITOR_OPUS_MODEL`, defaulting to `claude-opus-5`.
- Generalizes `_run_assignment_editor()` so the exact same assignment contract can be executed with either Sonnet 5 or Opus 5.
- Adds a shared publication-isolated variant runner so both challengers receive identical downstream treatment.
- Runs Sonnet 5 and Opus 5 independently against each queued category packet.
- Keeps Sonnet 4.5 as the writer for both challenger paths so writing quality is held constant.
- Blind review now randomizes **A / B / C** independently per category.
- Answer key reveals all three paths only after scoring.
- Machine report schema advances from 3 to 4 and includes explicit `variants`, `variant_comparison_signals`, Opus assignment diagnostics, raw/final Opus output, durations, actual model IDs, and final source mapping.
- A failure in either challenger makes the full three-way category comparison unscoreable rather than silently reducing it to a two-way comparison.
- Preserves the historical Sonnet challenger fields for report compatibility.
- Adds Claude Opus 5 standard/global list pricing to model-usage observability: $5/M base input and $25/M output, with corresponding prompt-cache rates.
- Updates the Generate News checkbox description to identify the three-way experiment.

## Source-integrity inheritance

v1.13.6.7r remains authoritative. Both Sonnet 5 and Opus 5 final projections use the same post-canonical source-integrity contract. A numeric `source_index` alone cannot validate a rebound, and a mismatched final story fails closed as `FinalSourceMappingError`.

## Permanent regressions

1. The blind artifact contains three variants and does not leak Sonnet/Opus model identities before the answer key is opened.
2. The answer key contains exactly production, Sonnet 5 editor + Sonnet 4.5 writer, and Opus 5 editor + Sonnet 4.5 writer.
3. `_run_assignment_editor()` routes `claude-opus-5` through the same assignment-only prompt contract.
4. The three-way runner remains post-build and cannot append live categories or write the generation cache.
5. Final source mapping remains authoritative for the Sonnet path and is independently recorded for the Opus path.
6. Opus 5 usage receives current list-cost accounting instead of an unknown-model/null-cost report.

## Validation

- Package validation: 38 modules imported / 122 public exports verified.
- Focused assignment-editor + model-usage suites: 36 passed.
- Full editorial test gate: 1,021 passed / 0 failed.
- Existing warnings only: 41 `datetime.utcnow()` deprecation warnings.

## Production validation target

Run **Generate News** manually with `assignment_editor_shadow=true` and `model_bakeoff=false`.

Expected log signature:

`Assignment-editor shadow: N live-generated category packet(s) queued; editors=claude-sonnet-5,claude-opus-5; writer=claude-sonnet-4-5-20250929; comparison=three-way-final-pipeline-aligned`

Then score `data/assignment-editor-shadow-review.md` before opening the answer key. The review should show Variant A, B, and C for every fully scoreable category.
