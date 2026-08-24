# Final Pipeline Stabilization Review Guide — v1.13.6.7i

## Test Editorial Engine
The normal Test Editorial Engine workflow should pass with the same exclusions already used by CI.

## First production run
Review these specific signals.

### Crime & Safety
If a generated/current hero is suppressed as an already-published duplicate, the section must not jump to an unrelated archive story while a valid surviving/current canonical story exists.

Good signals include:
- `Live-card hero recovery for Crime & Safety:`
- `Canonical duplicate recovery hero for Crime & Safety:`

The Aug. 24 Palm City barn-fire recovery must not recur in the same suppression scenario.

### St. Lucie County
The exact NWS tornado package that previously failed with:
`headline_jurisdiction_missing_from_lead`
should now pass when the headline says Port St. Lucie and the lead establishes St. Lucie County.

No special tornado exception exists; this is geographic containment logic.

### Final topic integrity
Inspect:
`data/final-topic-category-integrity.json`

Ideal natural run:
- `passed: true`
- `rejection_count: 0`

If it repairs a bad late mutation, the log will state:
`Final topic-category integrity removed ... invalid placement(s) after canonicalization`
The second pass must then be clean or deployment fails closed.

### Atomic canonical copy
Any category item rewritten to a canonical story must carry the canonical headline/teaser/body together. There should be no headline/body cross-story mismatch.

### Assignment-editor experiment
6.7f and 6.7h remain intact:
- topic-page category-fit adjudication stays enabled for the Sonnet 5 shadow;
- county pages do not get that extra topic adjudication;
- fresh follow-up heroes are not stale-swapped merely because the underlying event occurred the prior day.

Do not score a bakeoff if production still triggers a new unrelated invariant failure. If production and shadow both reach coherent final packages, scoring can resume.
