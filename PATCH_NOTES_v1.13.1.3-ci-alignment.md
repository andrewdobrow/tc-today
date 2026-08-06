# v1.13.1.3 CI Version Alignment

This overlay updates one stale regression assertion in `tests/test_incremental_generation_cache.py`.

The production workflow was intentionally advanced from bounded-runtime v1.9.5 to v1.9.6 by the generator runtime hotfix, but the cache workflow test still required the old v1.9.5 marker. The assertion now checks for:

`ACTIVE_WORKFLOW=tct-bounded-runtime-v1.9.6`

No runtime, editorial, registry, article, redirect, image, archive, or workflow behavior is changed by this overlay.
