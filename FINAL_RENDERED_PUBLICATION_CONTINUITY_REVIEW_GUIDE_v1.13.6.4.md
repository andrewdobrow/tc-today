# v1.13.6.4 review guide — final rendered publication continuity

## Expected production sequence

A healthy run may now print:

`Final rendered canonical projection self-healed N redirect link(s) and M duplicate card(s)`

when the rendered page exposes a repairable canonical collision. That message is a successful deterministic repair, not a warning that deployment is unsafe.

It must then continue through:

- `Final canonical surface contract PASSED`
- `Homepage permalink uniqueness PASSED`
- presentation checks and remaining site generation
- workflow commit/deployment steps

## Safety properties

- The final strict canonical validator is not removed or weakened.
- Only primary homepage grid-card anchors are removed by the repair pass.
- The visible lead hero is never dropped; a redirect-source hero is rebound to its direct canonical URL.
- Duplicate removal is based on the same persisted archive/redirect identity context used by the validator.
- No archive, story registry, cache, category membership, ranking policy, membership entitlement, or article body is modified by this release.

## Permanent regression

`tests/test_final_canonical_surface_dedup.py::test_rendered_projection_self_heals_live_item_identity_drift_before_final_gate`

The release-coherence test also requires the repair-before-validator ordering so a future stale generator replacement cannot silently erase this production-continuity boundary.
