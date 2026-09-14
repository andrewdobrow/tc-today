# TCT v1.13.9.23 — editorial registry storage headroom

## Production failure addressed

The production generator stopped before writing `data/editorial_story_registry.json` because the compacted registry reached 50.03 MiB, just over the existing 50 MiB safety ceiling.

This patch does **not** raise or disable the safety ceiling and does **not** discard authoritative story records.

## Change

`StoryRegistry` now omits six deterministic runtime cache fields from the on-disk JSON only:

- `lifecycle`
- `importance`
- `editorial_proximity`
- `editorial_priority`
- `editorial_score`
- `score_breakdown`

Those values are already rebuilt deterministically by `_load()` every time the registry is opened. The live in-memory registry keeps them; only the persisted storage projection omits them.

`status` remains persisted because importance scoring consults prior status before lifecycle is recalculated during load.

The patch preserves story IDs, event mappings, aliases, quarantine denylist/tombstones, canonical titles, source URLs, timelines, title candidates, resolver history, relationship history, incident evidence, and all other non-derived registry state.

## Safety / regression coverage

Added regression coverage proving that:

1. saving does not mutate the live registry;
2. only the explicitly recomputable cache fields are omitted from disk;
3. authoritative identity/history/provenance remains present;
4. omitted fields are rebuilt on reload; and
5. the storage projection creates headroom without raising `REGISTRY_MAX_BYTES`.

Validation on the reconstructed v1.13.9.22 tree:

- focused registry compaction tests: 12 passed;
- normal broad suite (same two legacy ignores): 1,333 passed, 0 failed.

On the latest available TCT registry snapshot, compact JSON falls from about 48.69 MiB to 44.07 MiB with this storage projection, reclaiming about 4.62 MiB without deleting authoritative story data.
