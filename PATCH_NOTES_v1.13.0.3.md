# TCT v1.13.0.3 — Generation Cache Source-Focus Integrity

## Why this release exists

The `v1.13.0.2` production workflow failed before generation because the Actions cache restore step replaced the repaired repository copy of `data/generation-cache.json` with an older cached file. That stale file still contained the WPBF shark-sighting source rewritten as a Martin County shark-fishing policy article, so the new repository-state regression correctly failed.

This was a workflow-state ordering defect, not a failure of the new source-focus assertion.

## Changes

- Moves the production Actions cache to the new `tct-generation-cache-v2-source-focus-*` namespace so no pre-guard cache can be restored.
- Runs `scripts/sanitize_generation_cache.py` after dependency installation and before package validation/pytest in both workflows.
- Removes the known pre-guard shark-video policy rewrite from any stale tracked or restored cache.
- Stamps cache files with `v1.13.0.3-source-focus-cache-integrity` and makes the migration idempotent and atomic.
- Bumps `CATEGORY_GENERATION_PROMPT_VERSION` to `v1.13.0.3-source-focus-cache-integrity`, making every category cache key created under the previous contract unreachable.
- Revalidates cached generated heroes and cards against the current publisher source row before reuse.
- Deletes a cached category immediately when its hero fails source-focus or article-framing integrity, forcing bounded regeneration instead of repeated reuse.
- Adds regressions for workflow step ordering, cache namespace isolation, stale-cache sanitation, atomic/idempotent migration, runtime cache loading, and current-source revalidation.

## Preserved behavior

- The valid August 1 WPTV shark-fishing policy update remains attached to the July 29 canonical article.
- The unrelated WPBF shark-sighting story remains a separate persistent story.
- No redirect changes are required.
- No changes were made to hero ranking or the pending Indian River placeholder work.

## Validation target

- Package validation succeeds.
- The complete editorial test suite succeeds after overlay application.
- A simulated legacy Actions-cache restore is sanitized before pytest and then passes the same suite.
