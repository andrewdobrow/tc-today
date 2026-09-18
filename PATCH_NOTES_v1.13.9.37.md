# TCT v1.13.9.37 — Registry Storage Projection v2

## Purpose
Permanently stop non-authoritative audit/cache growth from exhausting the 50 MiB editorial story registry safety ceiling.

## Root cause
The registry was persisting several large per-story fields indefinitely even though they are not required to restore story identity or publication authority after a process restart. As the candidate audit volume grew, those fields pushed the compacted registry to 50.05 MiB and aborted Production during the first category audit batch.

Largest avoidable persisted classes in the supplied production registry included resolution history, relationship history, lifecycle history, token caches, and rebuildable unified-incident evidence.

## Storage projection v2
The on-disk registry no longer persists:

- `resolution_history` — diagnostic only
- `relationship_history` — diagnostic only
- `lifecycle_history` — diagnostic only
- `title_tokens` — deterministically rebuilt from canonical title/titles on load
- `fact_tokens` — deterministically rebuilt from facts on load
- `unified_incident_evidence` — rebuildable from authoritative story content/timeline by the unified incident matcher
- existing deterministic ranking/lifecycle caches already omitted by storage projection v1

These fields remain usable in memory during the current process. They simply do not accumulate forever across runs.

## Explicitly preserved
Storage projection v2 does **not** remove or truncate:

- story IDs / next story ID
- event-to-story mappings
- story aliases
- quarantine denylist identity
- events
- timelines
- titles / canonical titles
- title candidates
- facts
- locations / agencies / event types / entities
- sources / URLs
- local relevance
- custom article counts
- incident anchors and other authoritative repair metadata

The 50 MiB hard ceiling remains unchanged.

## Size validation on supplied registry
- Existing file: 66,721,382 bytes (63.63 MiB)
- v2 normal pretty-JSON write: 36,203,153 bytes (34.53 MiB)
- Immediate headroom recovered: ~29.1 MiB
- Storage mode after v2 write: `normal / pretty_2`

Spot checks confirmed timeline, sources, canonical title, and events were preserved for representative large/previously problematic stories including `story_002044` and `story_010514`.

## Safety behavior
Pressure handling is now clearer:

1. Persist only restart-authoritative state via storage projection v2.
2. If still above the 45 MiB pressure threshold, reduce JSON indentation.
3. If still above 50 MiB, use compact lossless JSON.
4. Only fail if the **authoritative storage projection itself** exceeds 50 MiB.

The old pressure/emergency candidate-evidence compaction path was removed from size handling because unified incident evidence is no longer persisted.

## Validation
Focused registry/identity/story suites: **76 passed, 0 failed**.

The production-sized write simulation on the supplied real registry completed successfully at 34.53 MiB.

## Deployment
Apply this delta on top of v1.13.9.36.

Recommended sequence:
1. Run **Test Editorial Engine**.
2. If green, run **Production/Update**.
3. The first successful Production write will rewrite `data/editorial_story_registry.json` using storage projection v2 and reclaim the registry space automatically.
