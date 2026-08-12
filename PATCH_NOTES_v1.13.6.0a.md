# TCT v1.13.6.0a — deterministic WPTV regression fixture

- Fixes the single production-workflow pytest failure in `test_publisher_self_promotion_and_final_images.py`.
- The prior regression read mutable production `archive.json` and assumed the already-rejected WPTV meetup row still existed. If preflight or a prior cleanup had already removed that row, the test failed with `StopIteration` even though production state was correct.
- Replaces that mutable-live-data dependency with a fixed archive-shaped fixture mirroring the exact WPTV meetup publication.
- Continues to assert that the exact WPTV-branded meetup is detected as publisher self-promotion and is not archive-publishable.
- Does not change generator logic, publisher self-promotion rules, hero image enforcement, category contracts, county authority, membership, Stripe, or Supabase.

Validation:
- `python -m py_compile tests/test_publisher_self_promotion_and_final_images.py` — PASS
- `python -m pytest tests/test_publisher_self_promotion_and_final_images.py -q` — 7 passed
