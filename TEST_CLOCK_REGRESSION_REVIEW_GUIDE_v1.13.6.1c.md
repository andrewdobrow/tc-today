# v1.13.6.1c review guide

1. Confirm `tests/test_editorial_engine.py` no longer hard-codes 2026-07-20 as `DEFAULT_TIME`.
2. Confirm production code under `tct_engine/` is untouched by this overlay.
3. Run **Test Editorial Engine**.
4. Expected result: the two prior relationship assertions pass and the suite no longer depends on the calendar crossing a 30-day threshold.
