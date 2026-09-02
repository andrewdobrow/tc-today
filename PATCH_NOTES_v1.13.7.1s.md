# v1.13.7.1s — Exact Material-Update Receipt Contract Completion

## Basis

This increment was built from the user's freshly uploaded repository ZIP after v1.13.7.1r was applied. Unlike the prior reconstructed validations, this patch was developed and tested against the exact current checkout and its exact 1,104-test Test Editorial Engine suite.

## Failure reproduced

The exact current suite had one remaining failure:

`tests/test_published_story_skip_dedup.py::test_surviving_material_update_creates_target_and_hidden_commit_copy`

The surviving material-update target receipt already recorded `selection_surfaces` and `source_urls`, but did not persist the semantic decision's `novel_facts`. The same current test also requires the hidden publication receipt to be explicitly marked `_material_update_commit_only = True`.

## Correction

`scripts/generate.py` now:

- persists `novel_facts` on `CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS[canonical_slug]` from the validated `_semantic_material_update_decision`;
- backfills that field safely for any older in-process receipt row;
- marks hidden final-survivor publication receipts with `_material_update_commit_only = True` when they are created;
- reasserts `_material_update_commit_only = True` at the deterministic `_selected_material_update_commit_entries()` read boundary.

No identity, materiality, locality, freshness, quality, custom-authority, ranking, or publication thresholds were changed.

## Exact validation

On the freshly uploaded current repository:

- exact failing regression: passed;
- exact Martin motorcycle commit-queue regression: passed;
- exact GitHub Test Editorial Engine command:
  `python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`
  => **1,104 passed, 0 failed, 44 warnings**;
- `python -m py_compile scripts/generate.py`: passed;
- `python scripts/validate_package.py`: **38 modules imported / 122 public exports verified**;
- repository `+90 MiB` safety guard: clean.

The overlay itself was then applied to a fresh extraction of the uploaded repository ZIP and the exact same 1,104-test command was rerun successfully, proving the packaged overlay reproduces the green state.

## Next step

Apply v1.13.7.1s directly over v1.13.7.1r and run Test Editorial Engine. Only if the exact suite is green should Generate News run once for production validation.
