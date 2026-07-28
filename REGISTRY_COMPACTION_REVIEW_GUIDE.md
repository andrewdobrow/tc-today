# Registry Compaction Production Review

After applying v1.11.7.2 over v1.11.7.1, run the normal production workflow.

## Expected log indicators

Near editorial-engine initialization:

```text
Editorial registry history compacted: N -> M entries (D duplicates removed)
```

Before the commit step:

```text
Editorial registry size before commit: X.XX MiB
```

The first run should show a large duplicate-removal count and a registry size well below GitHub's 100 MB limit. Later runs should show little or no additional duplicate removal and stable file size.

## Verify

1. The workflow reaches `Commit and push` and GitHub accepts the push.
2. `data/editorial_story_registry.json` is below 50 MiB; approximately 4–7 MiB is expected from the current registry.
3. The registry still reports the same persistent story population and retains story timelines and source mappings.
4. No `tests/__pycache__` or `tct_engine/__pycache__` files appear in the commit.
5. The deployment job begins after the successful push.

## Compaction metadata

Inspect the top-level `history_compaction` object in `data/editorial_story_registry.json`:

- `last_load.entries_before`
- `last_load.entries_after`
- `last_load.duplicates_removed`
- `last_write.entries_after`
- `last_serialized_bytes`
- `max_serialized_bytes`

## Do not use Git LFS

The registry is generated structured state and should remain directly available to the workflow. Git LFS would mask the duplicate-history defect and complicate runtime access. The correct repair is deterministic compaction and bounded persistence.
