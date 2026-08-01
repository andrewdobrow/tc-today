# TCT v1.12.2.3 — Semantic Registry Consolidation

## Problem

v1.12.2.2 correctly removed five model-confirmed duplicate permalinks from the active archive and created canonical redirects, but the duplicate persistent story records remained active in `data/editorial_story_registry.json`.

That left publication surfaces clean while future source membership, lifecycle history and follow-up context could still split across parallel story IDs.

## Change

A validated semantic decision now authorizes one additional deterministic step:

- resolve the selected canonical slug to its retained archive story ID;
- merge the duplicate registry record into that canonical record;
- migrate sources, events, timelines, titles, entities and relationship history;
- write a permanent `story_aliases` mapping from the retired ID to the canonical ID;
- rebuild `event_to_story` so future source coverage resolves to the canonical story;
- retain an auditable `semantic_publication_gate_merges` entry on the canonical record.

Only decisions satisfying all of the following can write:

- `same_real_world_event = true`;
- `material_new_update = false`;
- action is `duplicate_use_existing_canonical`;
- confidence meets the configured semantic-gate threshold;
- the selected canonical slug still exists in the active archive;
- both source and target story IDs exist in the registry.

Material updates, uncertain decisions, custom articles and missing targets are not merged.

## Prior-run replay

The generator loads the previous completed semantic report before overwriting it. This allows the first v1.12.2.3 run to consolidate story fragments identified by the immediately preceding v1.12.2.2 production run even though their duplicate archive rows have already been removed.

## Diagnostics

`data/semantic-publication-gate.json` now includes:

- `summary.registry_story_records_merged`
- `summary.registry_aliases_written`
- `registry_consolidation`

The workflow log now reports the registry merge count alongside candidate pairs, Claude calls, redirects and holds.

## Production replay validation

The supplied v1.12.2.2 production artifacts produced five deterministic registry consolidations, including:

- `story_001684` → `story_001557` for the Port St. Lucie fatal crash;
- `story_001685` → `story_001316` for the Port St. Lucie officer resignation story.

No supplied directive was skipped.
