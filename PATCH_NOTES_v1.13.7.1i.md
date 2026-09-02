# TCT v1.13.7.1i — Accepted Material-Update Commit Queue Integrity

## Production failure addressed

The first production run inspected after v1.13.7.1h reached the archive writer, successfully routed the Tiger Woods plea development into the existing September 1 canonical, and recorded one committed semantic material update. The run then failed at the new terminal material-update publication invariant because the following separate Martin County target was recorded as selected but was absent from committed semantic material updates:

`2026-09-01-motorcycle-crash-shuts-down-i-95-southbound-near-hobe-sound-in-martin-county`

Source headline:

`Motorcycle crash shuts down I-95 Southbound in Martin County - WPEC`

This release preserves the fail-loud invariant. It corrects two deterministic handoff mechanisms in v1.13.7.1h that could create this exact selected-vs-committed mismatch.

## What changes

### 1. A generation attempt is no longer a publication selection

v1.13.7.1h recorded a terminal material-update obligation from `_carry_pre_generation_material_update_authority()` and `_stamp_current_run_story_ids()`.

Those functions run too early. Source attachment can occur inside a model generation attempt that later fails a prose guard and is retried, and identity stamping occurs before the immediate published-story suppression barrier.

v1.13.7.1i therefore separates **authority carry** from **accepted publication selection**:

- generated copy still receives target-bound material-update authority before prose guards so repair/recomposition remains possible;
- source attachment no longer mutates `CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS`;
- identity stamping no longer mutates that terminal invariant state;
- only hero/cards that survive the accepted category result and immediate published-story suppression are recorded as canonical commit obligations.

This prevents discarded generation attempts or subsequently suppressed placements from poisoning the terminal invariant.

### 2. Accepted material updates get a hidden canonical-write commit queue

Once an accepted hero/card carries a validated target-bound material update, a deep copy is retained in `CURRENT_RUN_SELECTED_MATERIAL_UPDATE_ITEMS`.

`write_archives()` adds those accepted items to an internal commit-only publication queue. This queue does not create a new live section placement. Its purpose is to ensure that later live-surface activation, ranking, or deduplication cannot silently erase already-selected editorial work before the canonical permalink writer sees it.

The terminal invariant remains authoritative: if the accepted update still cannot be committed safely, the run fails rather than pretending success.

### 3. Validated material-update copy outranks ordinary generated clones during publication coalescing

`_publication_copy_rank()` previously preferred image presence and hero status without giving any priority to a target-bound semantic material-update receipt.

That allowed an ordinary hero/image clone of the same persistent story to win publication coalescing over the actual update-bearing copy, stripping the semantic update authority before canonical write.

v1.13.7.1i now preserves the manual custom-article hierarchy while ranking a self-consistent validated material-update copy above ordinary generated hero/image copies of the same story.

### 4. Better terminal observability

Accepted target records now include:

- selection surfaces;
- source headline(s);
- source URL(s);
- source publication timestamp(s);
- semantic novel facts; and
- maximum semantic confidence.

The invariant policy is now labeled:

`every_accepted_validated_material_update_must_commit`

This makes a future terminal failure identify an accepted placement rather than an intermediate generation attempt.

## Regression coverage

New regressions verify that:

1. carrying material-update authority during a discarded generation attempt does **not** create a terminal publication obligation;
2. an accepted surviving material update creates both the invariant target and hidden commit copy;
3. a validated material-update copy outranks an ordinary image-bearing hero clone during publication coalescing; and
4. the exact September 2 Martin County motorcycle canonical/source combination that triggered the production invariant is retained by both the accepted-target tracker and commit queue.

The v1.13.7.1h Debevec regressions remain in place unchanged.

## Validation

Focused published-story/material-update suite:

- **40 passed**
- **0 failed**

Production-equivalent Test Editorial Engine suite:

`python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`

- **1,084 passed**
- **0 failed**
- 44 existing deprecation warnings

Package validation:

- **passed**
- 38 modules imported
- 122 public exports verified

Python compilation of the modified generator and regression test file passed.

## Production acceptance criteria

After applying v1.13.7.1i over v1.13.7.1h, run Test Editorial Engine first. If green, run exactly one Generate News workflow.

A successful production run should no longer fail merely because a discarded/retried generation attempt entered the invariant. If a validated material update survives the accepted category result, the log should show a material-update commit-queue acceptance and the canonical writer must either commit it or fail explicitly for a real downstream publication blocker.

The Tiger Woods canonical and the generated `data/material-update-publication-invariant.json` must be inspected after the first production run before this release is considered production-proven.
