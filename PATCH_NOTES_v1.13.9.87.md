# TCT v1.13.9.87 — registry fixed-point test alignment

Apply on top of **v1.13.9.86**.

## Why this patch exists
v1.13.9.86 intentionally stopped classifying a police/deputy PIT maneuver as evidence that the underlying incident was road rage. In the legacy named-death contamination regression fixture, that removes one unnecessary merge/split convergence cycle. The registry reaches the same clean fixed point in **2 passes instead of 3**.

The production behavior is correct: the fixture still verifies clean, still preserves the two distinct stories, and a second normalization is still a no-op. The only failure in the first v1.13.9.86 CI run was the stale exact pass-count assertion in `tests/test_registry_fixed_point_preflight.py`.

## Change
- Update `test_registry_preflight_does_not_rejoin_timeline_split_siblings_via_named_death` to expect `repair_passes == 2`.
- Add an explanatory comment tying the change to unified incident evidence v5 / PIT-maneuver road-rage hardening.
- No production code changes.
- No registry, archive, redirect, article, RSS, membership, image, or Bunny files are bundled.

## Validation
Focused:
- failing fixed-point regression + tow-yard regression suite: **9 passed**

Production-equivalent suite (same excludes used for local repo validation):
- **1,484 passed, 0 failed**

The two locally excluded legacy test modules require `engine.py`, which is not present in the reconstructed worktree; GitHub's uploaded run showed those modules passing before reaching this single stale assertion.
