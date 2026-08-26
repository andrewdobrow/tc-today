# v1.13.6.7o — Cumulative Release-State Convergence

This overlay repairs a mixed 6.7n repository state where the cumulative `scripts/generate.py`
was present but the 6.7m semantic-publication-gate implementation and stale-story regression
updates were not.

It is intentionally self-contained for repositories already on 6.7l or later. It re-applies the
complete files required by 6.7m and 6.7n so code, semantic publication authority, cleanup policy,
and regression tests converge to the exact validated state.

## Why this exists

The post-6.7n Test Editorial Engine run collected 996 tests and failed two stale-story assertions.
The expected cumulative state collects 1,004 tests. Reproducing repo + 6.7l + 6.7n produced the
same two failures. Adding the missing 6.7m companion files fixed both and restored all eight 6.7m
closure regressions.

## Functional policy retained

- Fresh publisher timestamps do not by themselves prove an old-event retouch.
- A stale retouch is proven by an older exact-source archive receipt unless validated update authority exists.
- Genuine next-day reporting (for example a Tuesday report about a Monday commission meeting) remains fresh.
- Terminal permalink authority from 6.7n remains intact.
- Dense shared-fact semantic candidate recall from 6.7m is restored.
- Existing tornado/trash duplicate cleanup policy from 6.7n remains intact.
