# TCT v1.13.9.30 — timeline-split negative identity guard

## Production failure fixed

The editorial registry preflight could repeat the same deterministic repair until the 16-pass safety ceiling and abort with a message such as:

`Registry preflight failed: deterministic repair did not converge within 16 passes. Last merges: {'story_002044': ('story_012322',)}`

## Exact root cause

The previous v1.13.9.29 patch correctly detached a moved timeline row from its secondary story, but it addressed only one half of the loop.

Production contained a legacy archived record (`story_002044`) with stale cross-source crash evidence and a bogus `named-person-death:tallahassee-democrat` anchor. A current Port St. Lucie crash record could be merged into that legacy record by verified cross-source incident evidence. Timeline-coherence repair then correctly split the incompatible shark/death row back into a separate story and wrote a durable split-lineage marker declaring the components different incidents.

On the next top-level pass, `_selective_named_person_death_repair()` did not honor that negative-identity marker. Because both split components could still resolve to the same legacy named-death anchor, the selective repair moved the death row back into the crash story. Timeline coherence split it again under a fresh story ID. The process repeated indefinitely:

`cross-source merge -> timeline split -> named-death move back -> timeline split -> ...`

This is why simply improving the moved-row detach identity did not make production converge.

## Fix

`_selective_named_person_death_repair()` now treats an existing timeline-coherence split lineage as stronger negative-identity authority than a named-person-death anchor.

When any stories participating in the same named-death anchor group share a durable timeline split root, that anchor group is treated as ambiguous and the selective repair fails closed instead of rejoining the split siblings.

This brings the named-person-death repair in line with the negative-identity protections already used by the exact/source/unified/incident merge layers.

The 16-pass ceiling is unchanged. No merge threshold was weakened and no pass limit was raised.

## Regression coverage

A new end-to-end regression reproduces the production pattern using the real `story_002044` failure shape:

1. stale archived shark/death record with cross-source crash evidence;
2. current Port St. Lucie crash record;
3. cross-source consolidation;
4. timeline-coherence split;
5. subsequent named-death repair.

With this patch the fixture converges in 3 repair passes, and an immediate second preflight is clean. Without the split-lineage guard, the fixture continually creates a fresh split story and never reaches a fixed point.

## Validation

- Fixed-point preflight tests: 8 passed.
- Registry/identity focused suite: 68 passed.
- Exact GitHub editorial pytest command: 1,341 passed, 0 failed.
- Exact production preflight entry point against a copy of the uploaded 64 MB registry: converged in 3 passes with `verification_clean: true`, 0 remaining source/unified/incident/timeline-coherence violations, and 12 duplicate story records removed.
