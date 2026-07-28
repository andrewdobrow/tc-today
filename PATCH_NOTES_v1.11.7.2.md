# TCT v1.11.7.2 — Registry History Compaction and Git Hygiene

## Production incident

The July 27 production run completed generation and created a local commit, but GitHub rejected the push because `data/editorial_story_registry.json` reached 103.90 MB, above GitHub's 100 MB per-file limit.

The registry's actual story data was not the cause. `resolution_history` appended the same resolver decision every time an already-known source was reconsidered in another category or later workflow run. An 81 MB production artifact contained 157,696 resolution-history rows but only 1,702 unique decisions.

## Repair

- Deduplicate exact `resolution_history` entries on registry load.
- Keep the newest 250 unique resolver decisions per story.
- Skip a new history append when the same evidence already exists.
- Compact merged story histories deterministically.
- Immediately rewrite the registry when load-time compaction removes duplicates.
- Enforce a 50 MiB post-compaction registry safety ceiling before writing.
- Record compaction metrics under the top-level `history_compaction` object.
- Print a concise production-log indicator when compaction occurs.

No stories, timelines, sources, events, aliases, entities, lifecycle state, or identity mappings are removed by duplicate-history compaction.

## Git workflow hygiene

- Set `PYTHONDONTWRITEBYTECODE=1` for the update job.
- Remove `__pycache__`, `.pyc`, `.pyo`, and `.pytest_cache` before committing.
- Add repository ignore rules for transient Python artifacts.
- Fail before commit when any generated file exceeds a 90 MiB repository safety ceiling.
- Print the editorial registry size immediately before the commit step.

## Production-artifact replay

A real 81,255,926-byte production registry was replayed through the patched writer:

- Stories retained: 624
- Resolution-history entries before: 157,696
- Unique entries retained: 1,702
- Exact duplicates removed: 155,994
- Resulting registry size: 4,726,664 bytes (about 4.51 MiB)

## Version

- Engine version: `1.11.7.2`
- Release: `registry-history-compaction-and-git-hygiene`
