# TCT v1.13.9.100 — Packard-only custom queue / suite-safe tests

This patch supersedes v1.13.9.99.

## Production behavior
- Keeps the current post-v1.13.9.98 `scripts/generate.py` with the Packard sponsored-article/carousel integration.
- `custom_articles.json` contains exactly one active custom article: Packard Roofing & Waterproofing.
- Does not restore the retired FDOT traffic custom article.
- Does not restore the retired St. Lucie Precincts 39/52 custom article.
- Preserves the clean Packard sponsorship treatment and four-image carousel.
- Does not restore the abandoned v1.13.9.96 polling-place identity experiment.

## Test corrections
- Replaces the stale St. Lucie custom-article test with a retirement assertion confirming that custom ID is absent from the active queue.
- Makes Packard queue tests read the repository `custom_articles.json` directly instead of the mutable `generate.OUTPUT_DIR` module global. This prevents order-dependent failures after tests that temporarily reassign `OUTPUT_DIR`.
- Packard queue test now requires Packard to be the sole active custom queue entry.

## Validation
- Exact six previously failing tests: 6 passed.
- Broader custom article suite: 43 passed.
