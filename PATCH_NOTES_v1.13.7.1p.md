# TCT v1.13.7.1p — Current-State Restoration + Accepted Material-Update Commit Queue Integrity

## Why this patch exists

The prior `v1.13.7.1i-accepted-material-update-commit-queue-integrity` overlay was built from an obsolete `v1.13.7.1h` `scripts/generate.py` instead of the actual current repository state, which had already advanced through the later `1i`–`1o` increments. Because that overlay contained a complete `scripts/generate.py`, applying it reverted later production code.

The Test Editorial Engine run exposed that regression directly: 13 failures, including missing/current-state functionality for authoritative custom material-update preservation, semantic material-update headline repair, category-hero Top Stories projection, the sitewide Mediavine loader, current membership copy, and persistent story-registry history compaction.

`1p` is a corrective cumulative overlay. It restores `scripts/generate.py` to the current `1o` line first, then ports only the intended accepted-material-update commit-queue correction on top of that current code. It also restores the current `tests/test_published_story_skip_dedup.py` before adding the new regression coverage, so the newer headline-invariant and custom-lock regressions are not lost.

## Material-update correction retained

The terminal material-update invariant remains fail-closed, but a terminal obligation is no longer created merely because a generated attempt inherited a validated source receipt.

A canonical update becomes an obligation only after the final category result survives the immediate generation/publication guards. This prevents a discarded/retried generation attempt from poisoning the end-of-run invariant.

Accepted target-bound updates are retained in a hidden canonical-write commit queue. Later surface ranking, activation, or cross-category deduplication can remove a visible placement without silently cancelling the already-accepted canonical update transaction.

When publication copies of the same persistent story are coalesced, a validated target-bound material-update copy outranks an ordinary generated hero/image clone. Custom payload priority remains above generated copies.

The existing `1j` headline progression contract is preserved: every accepted validated update must both commit and advance the canonical headline when the canonical headline is stale.

## Production regression covered

The Sept. 2 failure for:

`2026-09-01-motorcycle-crash-shuts-down-i-95-southbound-near-hobe-sound-in-martin-county`

is covered explicitly. Source attachment alone no longer creates the terminal obligation; an accepted surviving placement does, and the accepted copy remains available to `write_archives()`.

## Restoration verification

The exact feature families that failed after the stale overlay were re-run together with the material-update suite:

- authoritative custom incident lock
- sitewide Mediavine loader
- membership UI dark launch
- semantic material-update routing/headline repair
- persistent story-registry history compaction
- Top Stories category-hero freshness projection
- published-story/material-update deduplication

Result: **79 passed, 0 failed**.

Production-equivalent Test Editorial Engine command:

`python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`

Result: **1104 passed, 0 failed**, 44 existing deprecation warnings.

Package validation:

`python scripts/validate_package.py`

Result: **passed — 38 modules imported, 122 public exports verified**.

`python -m py_compile scripts/generate.py` also passed.

## Files

- `scripts/generate.py`
- `tests/test_published_story_skip_dedup.py`
- `PATCH_NOTES_v1.13.7.1p.md`

## Production acceptance

This patch is locally/workflow validated but is not considered production-proven until one real Generate News run completes successfully. For the next run, verify:

1. the terminal material-update invariant no longer fails on the Martin County motorcycle story unless a genuinely accepted update is actually lost;
2. Tiger Woods updates selected by the live writer are committed to the existing canonical and the headline/body advance appropriately;
3. `data/material-update-publication-invariant.json` reports the accepted canonical obligations and passes;
4. no later guard removes a validated accepted update before canonical write.
