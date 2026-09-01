# TCT v1.13.7.1f — Promoted material-update duplicate-guard authority fix

## Why this release exists

The Sept. 1 production run exposed a direct contradiction at the pre-generation source boundary for the Michael Anthony Debevec II missing-person story.

The WPTV source `Martin County Sheriff's Office investigates body found in Hutchinson Island mangroves` was correctly resolved to the existing Aug. 29 authoritative custom canonical and correctly adjudicated as a major material update. The semantic gate returned `validated`, `update_existing_canonical`, and confidence up to 1.00, with novel facts including the recovered body, matching clothing, the House of Refuge location, Medical Examiner review, and pending positive identification.

However, `_promote_published_skip_material_updates()` stamped the source as an authorized canonical update and then the immediately following `_filter_published_skip_candidates()` called `_published_skip_canonical()` again. Because durable custom identity deliberately continues to resolve an authorized update to its existing custom canonical, the no-change duplicate guard suppressed the very source the material-update gate had just promoted.

Production therefore performed the contradictory sequence:

1. `promoted: true` / `action: update_existing_canonical`
2. same URL immediately suppressed as `registry_skip_story_already_published`
3. source never reached generation
4. `material_updates_applied` remained `0`
5. the Aug. 29 missing-person canonical remained unchanged

This was not a materiality-model failure. The editorial decision was correct; the write pipeline discarded the authorized transaction before composition.

## Fix

`_filter_published_skip_candidates()` now distinguishes a true no-change duplicate from a source that already holds a target-bound pre-generation material-update authorization.

A source is preserved only when all of the following are true:

- `_semantic_material_update` is set;
- `_pre_generation_material_update_promotion` is set;
- the stamped promotion target exactly equals the canonical slug resolved by the duplicate guard; and
- `_canonical_write_authorized(item, canonical)` still validates the target-bound write authority.

Only then does the source bypass this no-change suppression point. Ordinary `skip` sources remain suppressed exactly as before.

This is intentionally fail-closed: a route label alone cannot bypass duplicate suppression, an unstamped semantic result cannot bypass it, and an authorization for a different canonical cannot bypass it.

## Production-state replay

The fix was replayed against the actual WPTV Debevec source stored in the uploaded production repository and the actual semantic-publication cache from that repository.

Result:

- material-update promotion: `1`
- semantic cache hit: `1`
- model calls required: `0`
- source after duplicate guard: **kept = 1, suppressed = 0**
- source-depth contract: **publishable**
- Martin County category contract: **eligible**
- Crime & Safety category contract: **eligible**

Before this fix, the same production source was present in both the promotion and suppression lists in the same category-generation report.

## Regression coverage

Added a Debevec-specific regression using the Sept. 1 body-recovery event shape. It verifies the complete critical sequence:

`validated material update -> promotion stamp -> immediate published-story guard -> source retained -> source remains publishable`

Existing no-change duplicate suppression tests remain green.

## Validation

- Python compile: passed.
- Focused missing-person + published-story suppression tests: **46 passed**.
- Exact Test Editorial Engine workflow-equivalent suite: **1,070 passed / 0 failed**.
- `python scripts/validate_package.py`: passed — **38 modules imported, 122 public exports verified**.
- Actual production Debevec source replay: passed through promotion, duplicate guard, source depth, Martin County eligibility, and Crime & Safety eligibility.

## Deployment

Apply this ZIP at repository root over v1.13.7.1e.

Run **Test Editorial Engine** first. If green, run **Generate News**. The next Generate News run should no longer show the WPTV Debevec URL simultaneously as a promoted material update and as `registry_skip_story_already_published` at the immediate pre-generation guard.
