# TCT v1.13.7.0b — Timeline Split Negative Identity Authority

## Production failure

Registry preflight failed after 16 deterministic passes with a final merge like:

`story_006228 <- story_007107`

The failure is a split/merge fixed-point oscillation, not evidence that the safety ceiling is too low. A high-confidence timeline-coherence repair can split one contaminated legacy story into multiple incompatible incidents. Later whole-record identity layers (exact/publisher-normalized title, exact source URL, unified incident identity, or incident identity) could then reconnect the newly separated siblings using weaker legacy evidence. The next top-level pass split them again under a fresh story ID, creating an unbounded cycle.

The latest available production registry also shows why story_006228 is a plausible trigger: it carries unrelated Palm Bay death coverage under historical `named-person-death:palm-bay` contamination.

## Fix

- Bump registry repair contract to v15.
- Persist `timeline_coherence_split_roots` on every component created by a high-confidence timeline split.
- Treat a shared split root as durable negative identity authority: two sibling components cannot be whole-record merged by weaker identity evidence.
- Preserve the split root when either component later merges into a stronger external canonical, preventing a third record from bridging the siblings back together transitively.
- Apply the negative-identity guard to:
  - exact / publisher-normalized title components,
  - exact safe source-URL components,
  - unified incident components,
  - conservative incident components.
- Existing historical split records remain protected even if they predate the new field; `timeline_coherence_repair.original_story_id` is recognized as the same lineage evidence.
- Registry-health duplicate counts no longer flag deliberately separated timeline siblings as unresolved mergeable duplicates.
- Keep the 16-pass ceiling unchanged.

## Regression coverage

- Two timeline-split siblings with identical weak title evidence remain distinct and registry health reports clean.
- Negative split lineage propagates when a stronger third-party/custom canonical becomes primary.
- Fixed-point preflight regression reproduces the `006228 -> 007107` class of oscillation: a split fragment that would previously be remerged now survives and preflight converges on the second pass.

## Validation

- `python scripts/validate_package.py`: 38 modules / 122 exports validated.
- CI-equivalent suite: 1,053 passed / 0 failed / 44 existing datetime warnings.

No production data file is included in this overlay. The existing production preflight performs the deterministic repair using the corrected authority rules.
