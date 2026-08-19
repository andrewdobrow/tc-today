# v1.13.6.1d — Registry pressure serialization hotfix

## Production failure addressed

The Aug. 19 production run aborted while flushing the deferred Local Government editorial-audit batch:

`RuntimeError: Editorial story registry exceeds the 50 MiB safety ceiling after adaptive candidate-evidence compaction: 50.19 MiB`

The hard 50 MiB guard is retained.

## Root cause

The registry writer always emitted two-space pretty-printed JSON. At current registry scale, indentation alone consumes several MiB. Candidate-evidence compaction could therefore leave a semantically valid registry just above the safety ceiling even though the exact same JSON payload fits comfortably below the ceiling with tighter whitespace.

## Fix

`tct_engine/story_registry.py` now uses adaptive, lossless serialization:

- normal mode: two-space JSON, unchanged;
- pressure mode: existing pressure evidence compaction plus one-space JSON;
- emergency mode: existing emergency evidence compaction plus compact JSON separators;
- the 50 MiB hard ceiling remains fail-closed after the lossless storage steps;
- `history_compaction.last_serialization_mode` records the representation used.

No story IDs, event mappings, canonical titles, timelines, quarantine rules, lifecycle rules, relationship rules, follow-up enforcement, ranking, membership, or publication behavior are changed by this hotfix.

## Regression coverage

`tests/test_editorial_registry_compaction.py` adds a case that places the safety ceiling between the two-space and one-space representations and verifies that pressure-mode save succeeds without changing story identity, event mapping, or entity data.
