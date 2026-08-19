# TCT v1.13.6.4 — final rendered publication continuity

## Incident

On Aug. 19, 2026, the production generator completed archive publication identity, story regression, persistent story identity, live permalink binding, forward live identity, category canonicalization, hero freshness, image repair, county authority, and live category canonical validation. It then rendered the homepage and aborted at the final canonical surface contract because one canonical-equivalent card remained.

## Root cause

The in-memory homepage deduper and the final rendered-page validator were observing different identity projections:

- the in-memory deduper had access to rich live card objects, including current-run incident metadata;
- the final validator intentionally reconstructs public identity only from rendered URLs plus persisted archive/redirect identity;
- live-only incident metadata could distinguish two cards in memory even when both persisted URLs belonged to one safe persistent story.

That allowed a card pair to survive the in-memory dedupe and then collapse to one canonical identity only after rendering.

## Fix

Adds `repair_final_canonical_surface_projection()` immediately after `render_index()` and before both homepage uniqueness validators.

The repair pass uses the exact same URL/archive-only identity projection as `validate_final_canonical_surface_uniqueness()` and deterministically:

1. rewrites a redirect-source lead hero to its direct canonical URL;
2. rewrites redirect-source grid cards to direct canonical URLs;
3. removes later grid cards canonically equivalent to the lead hero or an earlier card;
4. writes `data/final-canonical-surface-repair.json` for auditability;
5. leaves both strict validators in place after repair.

This is repair-before-fail, not fail-open publication. An unrepairable violation still stops deployment.

## Regression

Adds an exact regression for the production failure class: two live cards carry different current-run incident anchors while their persisted archive URLs share one safe story ID. The rich-object deduper keeps both, the un-repaired final validator fails, the new rendered-projection repair removes the duplicate, and the strict validator then passes.

## Validation

- workflow-equivalent test command: 896 passed, 43 existing warnings
- package validation: 35 modules / 119 exports
- generator runtime hotfix guard: PASS
- false-jurisdiction generator guard: PASS
- Python compilation: PASS
