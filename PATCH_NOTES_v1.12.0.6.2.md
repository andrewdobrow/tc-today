# Treasure Coast Today v1.12.0.6.2

## Cross-Source Identity Production Correction

This corrective release addresses false matches observed after the v1.12.0.6.1 workflow completed successfully.

### Fixed

- Restricts cross-source person identity evidence to explicit incident participants such as named victims, suspects, defendants, arrestees and sentenced individuals.
- Prevents quoted officials, agency spokespeople, publishers, location phrases and source branding from becoming person anchors.
- Adds exact production regressions for:
  - the Vero Beach fentanyl sentencing story versus the July 9 Sebastian deaths article;
  - the West Palm Beach police-union discipline story versus the Worth Avenue parking-impersonation case;
  - the Fort Pierce child sexual-battery case versus the Port St. Lucie roof-chase story.
- Adds a one-time exact-slug repair for the two canonical archive rows overwritten by the bad production matches.
- Restores the original static HTML for both affected canonical pages.
- Preserves the v1.12.0.6.1 candidate-blocking performance improvement.

### Repaired canonical pages

- `2026-07-09-second-decomposed-body-found-near-us-1-in-sebastian-days-after-first-discovery`
- `2026-07-30-two-arrested-after-high-speed-chase-through-port-st-lucie-ends-with-one-suspect`

The repair runs only when those exact slugs contain the known incorrect fentanyl-sentencing or sexual-battery content. Clean or legitimately updated rows are not changed.

### New report

`data/cross-source-identity-repair.json` records whether either corrupted canonical row was restored during the run.
