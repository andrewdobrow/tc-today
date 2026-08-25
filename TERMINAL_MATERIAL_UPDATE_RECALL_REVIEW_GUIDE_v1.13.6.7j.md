# v1.13.6.7j Production Review Guide

After Test Editorial Engine passes, run one normal production generation with the assignment-editor shadow enabled.

## Required checks

### Terminal material-update recall
If a newer source is resolved late to an existing canonical, inspect `data/semantic-publication-gate.json` for `late_published_skip_materiality_decisions`.

For a true material follow-up, expect:
- `evaluated: true`
- `promoted: true`
- `action: update_existing_canonical`
- the exact existing canonical slug as the target
- a log line beginning `LATE MATERIAL UPDATE ROUTE: refreshed canonical page`

For a duplicate/no-change source, expect preservation of the existing canonical and no new URL.

### Port St. Lucie tornado regression
If the NWS confirmation remains in the source pool:
- it must not collapse to the old pre-survey `will conduct a storm survey` body merely because the story identity resolves late;
- a fresh completed `NWS confirms` source must not trigger a stale-hero swap solely because the underlying tornado occurred Sunday;
- the same canonical permalink may be retained, but the canonical article must contain the validated newer facts if materiality is confirmed.

### Shadow comparison
For a fresh official follow-up, `alignment_diagnostics.shadow.stale_hero_swap` should remain `null` unless a genuinely stale source is independently established.

### Existing production invariants
Confirm the usual gates remain green:
- Story regression production gate
- Persistent story identity integrity
- Forward/live permalink integrity
- Final county membership authority
- Live category canonical contract
- Final canonical surface contract
- Homepage permalink uniqueness

Do not update the Sonnet promotion scoreboard from a run whose production or shadow result is altered by an unresolved deterministic integrity failure.
