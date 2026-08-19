# v1.13.6.1e review guide

Review only the final-surface identity handoff.

1. Confirm `_dedupe_homepage_cards_by_permalink()` receives `hero_item=None` by default so existing callers/tests remain compatible.
2. Under `surface_context`, confirm hero identity uses the supplied live hero object rather than `{}`.
3. Confirm `canonicalize_all_live_category_surfaces()` passes its category hero as `hero_item`.
4. Confirm final homepage dedupe passes `top_cat["hero"]` as `hero_item`.
5. Confirm `validate_live_category_canonical_uniqueness()` still raises on any violation; added output is diagnostic only.
6. Run `tests/test_global_incident_identity_contract.py` and verify the live-only incident identity regression passes.
