# TCT v1.11.2.1 — Hurricane Guide Queue Hotfix

Apply this overlay over the current v1.11.2 repository.

## Root cause

The hurricane product guide was fully prepared in `content/hurricane-season-ready-product-guide.json`, but it was never merged into the live `custom_articles.json` publication queue. The production workflow calls `scripts/generate.py` directly and does not run the one-time installer, so the generator had no hurricane guide to load.

The retirement implementation was inspected and is already fail-closed: it matches exact normalized custom headline, an explicit `retired: true` flag, or an exact listed slug. No fuzzy, category, article-type, body, `unique_slug`, missing-ID, or generic-term retirement match was found.

## Changes

- Appends the 12-product hurricane guide to `custom_articles.json` while preserving the retired July traffic entry.
- Preserves the exact retired traffic headline and slug in `data/custom-retirements.json`.
- Adds a mixed-queue regression test proving the traffic entry is ignored while a `product_guide` with `unique_slug: true` remains active and normalized.
- Updates the observability footer to `v1.11.2.1 hurricane-guide-queue-hotfix`.
- Does not change custom overwrite authority, the authoritative custom incident lock, archive reconciliation, final identity gates, or permalink gates.

## Expected production log

The next production run should include lines equivalent to:

- `Custom articles loaded: 1`
- `Custom queue ignored 1 retired item(s)`
- `Custom article: 'Hurricane Season Ready: 12 Treasure Coast Ess...' -> florida`
- an archive line showing one new article, unless an exact-headline edition already exists
- `Custom exact-headline permalink verified ...`
- `TCT Editorial Engine — v1.11.2.1 hurricane-guide-queue-hotfix`

## Validation completed locally

- Package import validation passed: 29 modules and 98 public exports.
- Focused custom/product/incident/permalink/observability tests: 27 passed.
- Workflow-equivalent local suite command: 287 passed, 14 deprecation warnings.
- Repository dry run loaded exactly one active custom article: the 12-product hurricane guide; the retired traffic item was ignored.

These are local results. GitHub Actions and a production generation/deployment run have not been executed from this environment.
