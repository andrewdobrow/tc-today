# v1.13.7.1r — Material-Update Commit Receipt Contract Completion

## Why v1.13.7.1q still failed CI

The exact GitHub Test Editorial Engine run after 1q reduced the material-update failures from four to two, but exposed two contract details that the 1q reconstruction had not exercised:

1. `CURRENT_RUN_SELECTED_MATERIAL_UPDATE_TARGETS[slug]` was missing the required `selection_surfaces` receipt (for example `martin:hero`).
2. `_selected_material_update_commit_entries()` — the public read boundary expected by the existing regression suite for the hidden commit queue — did not exist. `write_archives()` had equivalent inline iteration, but the contract expected a named deterministic helper.

This was a validation-process error in 1q: the candidate correction was tested against a reconstructed/older test checkout rather than the user's exact current 1104-test repository, so the surrogate tests did not cover these two interface expectations.

## Candidate correction

- `_remember_selected_material_update_target(item, selection_surface="")`
  - persists a deterministic `selection_surfaces` list on each canonical target receipt;
  - remains inert for provisional generation attempts because it is still called only from the final-survivor boundary.

- `_remember_surviving_selected_material_update_targets(data, category_key)`
  - preserves whether the accepted copy survived as `hero` or `card`;
  - records `category:surface` (for example `martin:hero` or `martin:card`);
  - stamps the hidden commit copy with `_material_update_selection_surface`.

- `_selected_material_update_commit_entries()`
  - is now the single deterministic read boundary for `CURRENT_RUN_SELECTED_MATERIAL_UPDATE_ITEMS`;
  - returns normal publication-entry tuples `(category_key, category_label, item)`;
  - returns deep copies so callers cannot mutate the per-run commit queue;
  - reasserts the target canonical slug and publication-only receipt flag.

- `write_archives()` now consumes `_selected_material_update_commit_entries()` instead of maintaining a second inline implementation of the queue reader.

No deterministic identity, materiality, locality, quality, custom-authority, or publication thresholds were weakened.

## Local validation

Built directly from the delivered 1q `scripts/generate.py`, then applied to the reconstructed 1p/q repository state:

- Python compile: passed
- focused publication/material-update tests: **52 passed**
- added local contract probes covering `martin:hero`, `martin:card`, helper return shape, deep-copy isolation, and repeated-surface dedupe: **3 passed**
- full reconstructed Test Editorial Engine equivalent including those probes: **1106 passed, 0 failed**
- package validation: **38 modules / 122 public exports**
- 90 MiB repository safety guard: clean

The user's exact current GitHub checkout contains a newer 1104-test `test_published_story_skip_dedup.py` that was not present in the last uploaded repository ZIP. This overlay intentionally does not replace that file. Therefore the exact 1104-test CI run remains the acceptance authority.

## Required next step

Apply **v1.13.7.1r over v1.13.7.1q** and run **Test Editorial Engine only**. Do not run Generate News unless the exact 1104-test suite is fully green.
