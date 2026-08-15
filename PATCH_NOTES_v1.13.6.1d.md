# Treasure Coast Today v1.13.6.1d — Martin cocaine duplicate identity hotfix

## Production regression

Two public TCT permalinks escaped for the same Martin County Sheriff's Office narcotics operation:

- Canonical, older URL: `2026-08-14-17-arrested-in-indiantown-cocaine-trafficking-ring-three-remain-wanted-after-mon`
- Duplicate, newer URL: `2026-08-15-17-arrested-in-martin-county-cocaine-trafficking-bust-4-kilos-seized-in-indianto`

Both describe Operation Beneath the Surface, 17 arrests, four kilograms of cocaine seized, and the same Martin County/Indiantown investigation.

## Root cause

Three independent defects combined:

1. `tct_engine/fact_extraction.py` used a raw substring check for `fire`, so `firearm`/`firearms` created a false `fire reported` fact and fire event family.
2. `_cross_source_event_families()` treated `seized` alone as an `animal-case` signal, so drug-seizure coverage could be mislabeled as animal coverage.
3. The final semantic retrieval gate shared five highly distinctive headline tokens for the production pair but scored 0.4928, narrowly below its 0.50 moderate-candidate threshold. There was no dedicated continuity path for a named law-enforcement operation or a same-agency/same-locality drug operation.

## Fix

- Fire fact extraction now requires an actual standalone fire-event term and no longer matches `firearm`/`firearms` by substring.
- `seized` alone no longer creates `animal-case` identity.
- Added deterministic `drug-case` cross-source family evidence.
- Added `Indiantown` to source/locality identity extraction.
- Added durable named law-enforcement operation anchors such as `law-enforcement-operation:beneath-the-surface`.
- Semantic candidate retrieval now allows a conservative candidate-only path when:
  - a named law-enforcement operation anchor matches, or
  - same locality + same agency + `drug-case` + shared arrest/drug/numeric headline evidence establish strong operation continuity.
- These paths only nominate a pair for the existing semantic adjudication gate; they do not directly fuzzy-merge unrelated stories.
- Semantic publication gate version bumped from 1.4 to 1.5 so stale candidate-decision cache entries cannot hide the new retrieval behavior.

## Existing URL repair

A verified migration fallback runs only if the generalized semantic repair did not already resolve the exact production pair. It:

- preserves the Aug. 14 permalink as canonical;
- converts the Aug. 15 permalink to the canonical redirect path;
- removes the Aug. 15 duplicate row from archive-driven surfaces;
- retains the URL as a permanent redirect rather than deleting it;
- records the verified production regression in semantic/publication diagnostics.

This migration is not the prevention mechanism; the prevention is the generalized identity work above.

## Validation

- Exact production regression and focused identity suite: 40 passed.
- Broader identity/publication suite: 119 passed.
- Workflow-equivalent repository suite: 886 passed, 43 existing deprecation warnings.
- Package validation: 35 modules / 119 public exports.
- Generator runtime guard: PASS.
- False-jurisdiction guard: PASS.
- Redirect simulation on the fresh production repo confirmed:
  - canonical retained;
  - duplicate removed from archive surfaces;
  - duplicate HTML contains `noindex,follow` and `window.location.replace` to canonical;
  - `_redirects` contains a `301!` rule;
  - canonical article remains substantive.
