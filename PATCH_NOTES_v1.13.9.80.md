# TCT v1.13.9.80 — Weekend roundup guard + stale-generator recovery

## Why this patch exists

The prior weekend-roundup hotfix was generated from a stale copy of `scripts/generate.py` and therefore overwrote newer production work when applied. The resulting CI failures were real regressions: current Sonnet 5 configuration, article-content override behavior, Florida driver-license canonical protections, and Bunny article-image mirroring hooks were among the contracts displaced by the stale generator.

This patch restores the current v1.13.9.79 generator as the base and ports only the intended weekend-roundup/publication-clock changes onto it.

## Intended behavior retained

- Retire the Oct. 2 WPBF weekend roundup and redirect it to TCT's Oct. 3–4 curated guide.
- Retire the Sept. 25 WPBF weekend roundup and redirect it to TCT's Sept. 26–27 curated guide.
- Reject externally authored multi-event weekend roundups at feed ingestion, Things To Do eligibility, and final permalink publishability while exempting TCT custom/manual weekend guides.
- Stamp every genuinely new TCT permalink with the current TCT publication time instead of preserving an inherited older persistent-story timestamp.
- Merge `data/source-retirement-editor-overrides.json` additively with the existing baseline source-retirement cleanup policy.

## Explicitly preserved current production contracts

- Sonnet 5 production model configuration.
- Article content override and headline-only override behavior.
- Florida driver-license canonical/redirect protections.
- Bunny article-image mirror integration and v1.13.9.79 shadow observability refinements.
- Existing temporal source-fetch behavior and current source-fetch call signatures.

## Rollout

Apply this overlay on top of the repository state that received the broken weekend-roundup hotfix. Keep the existing Bunny mode setting unchanged. A successful production run should pass the full test suite before generation, then source-retirement cleanup should remove the two configured WPBF roundup duplicates from discovery/archive and write canonical redirects to the TCT guides.
