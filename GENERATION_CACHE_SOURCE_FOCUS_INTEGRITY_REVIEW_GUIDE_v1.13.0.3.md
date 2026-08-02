# Generation Cache Source-Focus Integrity Review Guide — v1.13.0.3

## Release identity

- Engine version: `1.13.0.3`
- Release: `generation-cache-source-focus-integrity`
- Category cache contract: `v1.13.0.3-source-focus-cache-integrity`
- Actions cache namespace: `tct-generation-cache-v2-source-focus-*`

## Files that matter

- `.github/workflows/update.yml`
- `.github/workflows/test-editorial-engine.yml`
- `scripts/sanitize_generation_cache.py`
- `scripts/generate.py`
- `data/generation-cache.json`
- `tests/test_generation_cache_source_focus_integrity.py`
- `tests/test_incremental_generation_cache.py`
- `tests/test_shark_policy_provenance_repair.py`

## Required workflow order

The production workflow must perform these steps in order:

1. Check out the repository.
2. Restore only the `v2-source-focus` generation-cache namespace.
3. Install dependencies.
4. Sanitize the persistent generation cache.
5. Validate the package.
6. Run the editorial test suite.
7. Run cleanup and generation.

The test-only workflow must sanitize the tracked cache after dependencies are installed and before package validation/pytest.

## Expected preflight output

A clean repository should print either:

- `Generation cache integrity: already clean.`
- `Generation cache integrity: stamped current integrity version; no unsafe entries found.`

A stale legacy cache may print that one unsafe category entry was removed. That is a successful migration, not a workflow failure.

## Production acceptance checks

- No `tct-generation-cache-v1-*` restore key appears in the production workflow.
- The shark-video source is not paired with an ordinance, commissioners, state-order, or state-directive headline in `data/generation-cache.json`.
- A cached hero that drifts from the current publisher source is rejected and regenerated.
- `story_001155` and `story_001783` remain separate.
- The canonical July 29 shark-fishing page retains only the valid WPTV policy update context.

## Review sequence

1. Apply the overlay at repository root.
2. Run **Test Editorial Engine**.
3. Run **Update Treasure Coast Today** only after the test workflow passes.
4. Review the test log for the cache sanitation line and full pass count.
5. Review `data/generation-cache.json`, `data/editorial_story_registry.json`, `archive.json`, and `data/persistent-story-identity-integrity.json` after production.

The Indian River placeholder hero remains a separate next increment after this production-state correction is verified.
