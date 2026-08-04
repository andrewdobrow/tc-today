# v1.13.0.4 — Persistent Timeline Coherence Integrity

## Purpose

Prevent unrelated incidents from sharing one persistent story timeline and using
that contaminated identity to suppress legitimate new coverage.

## Production repair

This release separates three confirmed timeline contaminations:

- Martin County Fire Rescue property-tax coverage from the unrelated Belle Glade fatal crash.
- Geoffrey Lang firefighter-death coverage from the unrelated Palm Beach County cat-and-hamster rescue.
- A Riviera Beach officer DUI arrest from the unrelated Loxahatchee Groves fatal shooting.

The St. Lucie firefighter hazing story, the Port St. Lucie Oxmoor Terrace shooting
updates and Florida's double-execution coverage remain grouped because they retain
strong headline or event-family continuity.

## Permanent protections

- Adds deterministic timeline-family and headline-continuity analysis.
- Splits only high-confidence incompatible timeline components.
- Rebuilds event-to-story mappings after a split without creating false aliases.
- Rejects future live follow-up attachments that present a hard timeline conflict.
- Adds timeline violations to persistent-story identity integrity and activation preflight.
- Prevents a currently incoherent story ID from authorizing published-story suppression.
- Adds production-state and unit regressions for the confirmed and preserved cases.

## Expected first production run

The registry reports three repaired records and three detached timeline entries.
Because registry state changes, activation may remain in shadow for that run. The
following clean run should report zero remaining timeline-coherence violations.
