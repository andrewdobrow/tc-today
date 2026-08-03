# Reader Support Recent-50 Preflight Hotfix v3

## Problem

The recent-50 overlay contained a repository-state regression asserting that the current 50 newest direct articles already used the support banner. Three articles created after the overlay package was built displaced three packaged pages, so the next workflow reached pytest before the bounded migration had a chance to normalize them.

This was a workflow-order defect. It was not a reason to expand the static migration back to hundreds of article files.

## Fix

- Runs the bounded recent-50 support-banner normalization before package validation and pytest in both `Test Editorial Engine` and the production update workflow.
- Keeps the migration limited to 50 direct article pages.
- Canonicalizes any existing article ad banner, not only the former `advertise-banner.png` markup.
- Replaces retained sensitive-topic house notices while reader-support mode is active.
- Inserts the support banner when a recent direct article has no banner slot.
- Uses atomic writes and verifies exactly one canonical banner slot remains.
- Leaves paid-advertising mode unchanged and preserves the sensitive-topic architecture for future commercial advertising.
- Adds regressions for legacy ads, sensitive notices, missing slots, idempotency and workflow ordering.

## Scope

This is an incremental hotfix for repositories that already have the recent-50 reader-support overlay. It contains no article HTML files and does not trigger a large GitHub upload.
