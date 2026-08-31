# TCT v1.13.7.0d — Semantic Decision Consistency Authority

## Purpose
Closes two production-proven semantic publication failures from the Aug. 31 run:

1. Waste Pro: model selected `recommended_action=update_existing_canonical` and supplied multiple concrete novel/corrective facts, but also emitted `material_new_update=false`; the validator silently converted the decision to duplicate and discarded the generated canonical refresh.
2. Indiantown flooding: Sonnet 5 identified the same event and a material update, but a long response truncated before the final `recommended_action` field. JSON repair recovered the core decision, then validation rejected it as `unknown_recommended_action`, causing a terminal HOLD.

## Changes
- Semantic publication gate version 1.8 -> 1.9.
- Prompt version 1.1 -> 1.2.
- Terminal permalink authority version 1.1 -> 1.2 to invalidate stale terminal cache entries under the corrected validator.
- `recommended_action` is now requested first in model JSON, not last.
- Model output budget increased from 900 to 1200 tokens for first-pass and resolution decisions.
- Missing `recommended_action` is deterministically recovered when the already-returned structured flags make the policy action unambiguous.
- Explicit `update_existing_canonical` + same-event + concrete `novel_facts` repairs a contradictory false auxiliary `material_new_update` flag to true, allowing the existing downstream composer/context contracts to decide whether the article can actually be rewritten.
- An explicit update with no novel evidence still fails closed.
- Decision reports now include `consistency_repairs` when a schema inconsistency was repaired.

## Safety
This does not loosen candidate retrieval, same-event confidence, identity thresholds, canonical URL authority, or custom-article protection. Update routing still requires a valid selected canonical and still passes through the existing material-update composer/context/write authorization layers.

## Validation
- Package validation: 38 modules / 122 public exports.
- CI-equivalent suite: 1,060 passed / 0 failed / 44 existing datetime warnings.
