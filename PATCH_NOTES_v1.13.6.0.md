# TCT v1.13.6.0 — Production editorial quality emergency gate

This release addresses three production-quality failures observed on Aug. 11, 2026.

## 1. Final live image contract

A hero/card can be promoted or rebound after the earlier editorial-image fallback pass. The final renderer previously had no invariant requiring that the newly selected hero still carry an image, which allowed the Causeway Cove front-page hero to render with an empty media panel.

- Adds `ensure_final_live_visual_images(...)` after late hero freshness, canonicalization and county-authority repair.
- Repairs any final live hero/card that is missing an image by using the existing deterministic editorial fallback selector.
- Writes `data/final-live-image-contract.json` for observability.
- Fails the production run closed if a real final visual placement cannot obtain an image.

## 2. Publisher self-promotion exclusion

The generation prompt already said TV/radio publisher self-promotion should not be published, but that instruction was not a deterministic publication boundary. The WPTV-branded `Let's Hear It` education meetup escaped the classifier and became a TCT article.

- Adds a narrow deterministic publisher-self-promotion detector for known news publishers.
- Rejects publisher-branded promotional events before article generation.
- Prevents an existing promotional article from archive recovery or final publication.
- Purges existing publisher self-promotion from the archive and replaces the old article URL with a `noindex,follow` archive redirect.
- Normal reporting from WPTV/WPBF/CBS12/etc. remains eligible; a publisher attribution suffix alone is explicitly not promotional evidence.

## 3. Crime & Safety / county projection cleanup

Current production data contained routine education stories carrying `Crime & Safety`, and the Indian River bus-routing story was projected into Martin, St. Lucie and Indian River counties even though the generated story focus was specifically Indian River County.

- Promotes Crime & Safety from observe-only to an enforced visible-focus contract.
- Revalidates stale Crime & Safety memberships at the shared projection boundary.
- Preserves legitimate crime and public-safety variants including sentencing, drowning, theft, rescue and fire coverage.
- When source evidence is regional but the generated display headline explicitly narrows to exactly one Treasure Coast county, final county membership follows that single-county editorial focus.
- If an invalid enforced primary category is removed and a valid membership remains, the archive primary category is repaired to the surviving category.

## Regression coverage

New/updated regressions cover:

- the exact Aug. 11 WPTV meetup archive row;
- WPTV attribution-suffix false-positive protection;
- the exact blank Causeway Cove hero condition after late reselection;
- fail-closed behavior when no final image can be found;
- routine Indian River reading-proficiency and bus-routing stories rejected from Crime & Safety;
- legitimate school safety stories retained in Crime & Safety;
- generated Indian River-only focus narrowing a regional source to Indian River County.

## Validation

- `python scripts/validate_package.py`: PASS — 35 modules / 119 public exports.
- `python scripts/apply_generator_runtime_hotfix.py --check`: PASS.
- `python scripts/apply_false_jurisdiction_hotfix.py --check`: PASS.
- Workflow-equivalent runnable suite excluding the two test files whose fixture requires the absent root `engine.py`: 876 passed.
- Focused emergency suite: 90+ passed during development; final targeted suite 42 passed after false-positive hardening.
- Python compile: PASS.
- Python 3.11 grammar parse: PASS.

The uploaded production ZIP does not contain root `engine.py`; therefore the seven tests in `test_canonical_identity.py` / `test_matcher_contract.py` that require that fixture cannot initialize locally. This is a source-package limitation, not a failure introduced by this release. The GitHub production workflow remains the Python 3.11 integration gate.
