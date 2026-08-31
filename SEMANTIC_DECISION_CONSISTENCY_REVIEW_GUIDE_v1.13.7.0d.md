# Review guide — v1.13.7.0d

After Test Editorial Engine is green, run Generate News once.

Verify in `data/semantic-publication-gate.json`:

1. No high-confidence same-event decision is held solely for `unknown_recommended_action` when the structured same-event/material flags are otherwise complete.
2. Waste Pro-style decisions that explicitly recommend `update_existing_canonical` and provide concrete novel facts route as an update rather than being silently downgraded to duplicate because of a contradictory auxiliary flag.
3. `consistency_repairs` is populated whenever such deterministic schema recovery occurs.
4. Custom canonicals remain canonical and are only refreshed through target-bound update authority.
5. Terminal permalink HOLD remains fail-closed for genuinely ambiguous identity or sub-threshold confidence.

Expected Test Editorial Engine count on this patch state: 1,060 passed.
