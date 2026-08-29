# v1.13.6.8a — Quarantine tombstone registry compaction hotfix

## Production failure addressed

Generate News aborted during the Local Government editorial-audit batch while flushing the persistent story registry:

`RuntimeError: Editorial story registry exceeds the 50 MiB safety ceiling after adaptive candidate-evidence compaction and lossless JSON compaction: 50.02 MiB`

The 50 MiB hard ceiling remains unchanged.

## Root cause

The active story registry was not the dominant new source of pressure. Historical `quarantined_stories` were retained as complete story snapshots even though quarantined records have no publication authority and runtime denylisting depends on their story IDs. In the current repository, 631 quarantine snapshots consumed roughly 14.7 MiB of the compact registry. The registry was already approximately 49.91 MiB in compact form; one additional quarantine pushed the next write over the safety ceiling.

## Fix

`tct_engine/story_registry.py` now converts historical quarantine snapshots into deterministic audit tombstones before serialization. Each tombstone preserves:

- story ID;
- canonical title;
- event keys;
- status;
- quarantine timestamp and reasons;
- repair version;
- representative title/source samples;
- counts of discarded diagnostic collections;
- SHA-256 of the original full snapshot.

Large non-authoritative diagnostic payloads such as full timelines, resolver history, relationship history, candidate evidence and complete title/source lists are no longer retained indefinitely inside the primary registry after quarantine.

The mapping key remains the permanent denylist authority, so quarantined IDs still cannot re-enter publication identity.

## Current-registry reproduction

Against the current repository registry:

- active stories: 5,408 -> 5,408;
- event mappings: 8,012 -> 8,012;
- quarantine IDs: 631 -> 631;
- quarantine snapshot payload: ~14.72 MiB -> ~1.07 MiB;
- quarantine bytes reclaimed: ~13.66 MiB;
- saved registry after normal writer pressure handling: ~44.68 MiB;
- hard ceiling: 50 MiB, unchanged.

No story identity, ranking, generation, membership, canonicalization, dedupe, publication or assignment-editor behavior is changed.

## Validation

- focused registry/identity suite: 89 passed;
- full CI-equivalent editorial suite: 1,023 passed, 0 failed;
- existing warnings: 41 `datetime.utcnow()` deprecation warnings.
