# v1.13.7.1q — Surviving Material-Update Commit Queue Integrity

## CI failure addressed
After v1.13.7.1p, Test Editorial Engine exposed four existing material-update transaction regressions:

- provisional model-attempt copy incorrectly created a terminal commit obligation;
- the final-survivor commit helper was missing;
- an ordinary hero/image clone could outrank the validated update copy during publication coalescing;
- the September 2 Martin County motorcycle update receipt could therefore be lost before the canonical commit queue.

These failures are related to the same transaction-boundary problem: material-update authority was being *remembered too early* while generated copies were still provisional, yet the final accepted copy was not given a durable hidden publication receipt after all category gates had completed.

## Candidate correction

1. **Provisional carry is no longer a commit event.**
   - `_carry_pre_generation_material_update_authority()` still copies the exact target-bound semantic/write authority into generated copy.
   - It no longer writes `CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS`.
   - `_stamp_current_run_story_ids()` likewise no longer creates the terminal obligation merely by restamping an item.

2. **Adds a final-survivor transaction boundary.**
   - `_remember_surviving_selected_material_update_targets(data, category_key)` runs only after the final category quality gates and published-story suppression boundary.
   - Only surviving hero/card copies with self-consistent target-bound material-update authority create the terminal commit obligation.

3. **Adds a hidden commit receipt.**
   - `CURRENT_RUN_SELECTED_MATERIAL_UPDATE_ITEMS` stores one deep-copied accepted publication receipt per canonical slug.
   - The receipt is publication-only and is never added back to visible category/homepage surfaces.
   - `write_archives()` appends those receipts to its publication input so later surface coalescing cannot silently erase the only authorized update copy.

4. **Validated updates outrank stale presentation clones.**
   - `_publication_copy_rank()` now distinguishes a current manual queue submission from durable custom provenance.
   - Current manual queue copy remains highest authority.
   - A validated target-bound material update outranks ordinary hero/image/body-length preferences and durable non-queue presentation clones.

5. **Repairable protected updates can reach recomposition.**
   - A hidden receipt already queued for grounded semantic recomposition may pass the pre-permalink thinness check.
   - Dangerous topic/jurisdiction failures remain fail-closed; this does not weaken those guards.

6. **Per-run state remains isolated.**
   - Both selected-target and hidden-item maps reset at the start of every Generate News run.

## Validation
Against the reconstructed v1.13.7.1p repository state:

- reconstructed exact failure semantics: **4 passed**
- full Test Editorial Engine equivalent: **1103 passed, 0 failed**
- package validation: **38 modules / 122 public exports**
- Python compile: passed
- repository 90 MiB guard: clean

The user's current GitHub checkout already contains the four exact failing regression tests shown by CI, so this overlay intentionally does not replace that test file with an older local copy.

## Production acceptance
After applying over v1.13.7.1p:

1. Run **Test Editorial Engine**. The four existing regressions must pass and the workflow must be fully green.
2. If green, run exactly **one Generate News**.
3. Confirm:
   - no discarded/retried generation attempt creates a false terminal material-update invariant;
   - surviving validated updates log a material-update commit-queue receipt;
   - the existing Debevec August 29 canonical remains the only canonical URL for that story;
   - Martin County motorcycle and other validated updates are not erased by hero/card coalescing;
   - `Custom RSS publication contract PASSED`;
   - `Material-update publication invariant PASSED` when a surviving validated update is selected;
   - overall Generate News exits successfully.
