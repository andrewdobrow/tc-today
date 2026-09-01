# TCT v1.13.7.1e — Pre-archive material-update scope hotfix + contaminated cross-source authority hardening

## Why this release exists

v1.13.7.1d correctly moved generated/cached published-story placements behind a late material-update decision before destructive suppression, but the production integration passed `semantic_report=_semantic_gate_report` from `main()`. `_semantic_gate_report` is local to `write_archives()`, so a live category reaching that new call path raised `NameError` before publication.

The same failed run also exposed an independent identity-safety issue: a WPEC Fellsmere machete-stabbing search source was write-authoritatively matched to an unrelated Port St. Lucie missing-person canonical through the `precise_location_plus_distinctive_facts` composite. The incoming and canonical headlines shared only one topical concept (`search`). This is consistent with publisher-page related-story contamination contributing a street/fact overlap that does not belong to the headline event.

## Fix 1 — make the v1.13.7.1d material-update protection runnable in production

- `main()` now creates a main-scoped pre-archive semantic report for generated/cached placement suppression.
- Both `_suppress_published_skip_placements()` call sites use that report instead of the `write_archives()` local variable.
- The report is handed across the phase boundary through a one-run module state object and consumed by `write_archives()`.
- `write_archives()` merges the pre-archive late-materiality rows/counts into the persisted semantic publication report, preserving observability.
- The existing `write_archives(all_categories, top_cat)` call contract is unchanged so the post-publication permalink ordering contract remains intact.

## Fix 2 — stop related-story body contamination from granting cross-source write authority

The `precise_location_plus_distinctive_facts` authority path now additionally requires at least **two shared headline topic concepts**.

This is deliberately narrow:

- Named-person composites are unchanged.
- Exact incident/known-event identity is unchanged.
- Genuine same-incident precise-location matches remain authorized when their headlines share at least two event concepts.
- A publisher page that embeds an unrelated related-story module can no longer gain destructive canonical authority from one coincidental headline concept plus contaminated body facts.

## Regression coverage

Added/updated tests verify:

1. `main()` never references the `write_archives()`-local `_semantic_gate_report`.
2. Both generated/cached placement suppression calls use the main-scoped semantic report.
3. The existing `write_archives(all_categories, top_cat)` publication-order contract is preserved.
4. Precise-location + body-fact overlap with only one shared headline concept is candidate-only and cannot authorize a canonical write.
5. The same composite remains write-authoritative with three shared headline concepts, preserving legitimate use.
6. v1.13.7.1d's major-update-before-suppression regressions remain green.

## Validation

- Python compile: passed.
- Focused new/affected tests: **37 passed**.
- Missing-person / cross-source / semantic / publication targeted suite: **162 passed**.
- Workflow-equivalent pytest command: **1,069 passed / 0 failed**.
- `python scripts/validate_package.py`: passed — 38 modules imported, 122 public exports verified.

## Deployment

Apply this ZIP at repository root. It is safe to apply over either the pre-v1.13.7.1d repository or a repository where v1.13.7.1d was already uploaded because the release includes the complete corrected `scripts/generate.py`.

Run **Test Editorial Engine** first. Only run **Generate News** after the test workflow is green.
