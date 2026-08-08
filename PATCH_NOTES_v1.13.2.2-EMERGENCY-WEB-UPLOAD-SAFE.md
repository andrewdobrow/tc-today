# Treasure Coast Today v1.13.2.2 Emergency Web-Upload-Safe Overlay

## Immediate production failure fixed

Production aborted during the first category audit because `data/editorial_story_registry.json` exceeded the 50 MiB hard safety ceiling after the existing resolution-history compaction. The observed failure was 50.55 MiB.

The registry was retaining up to 24 full `unified_incident_evidence` payloads per story. These rows are candidate/diagnostic relationship evidence; they are not authoritative story IDs, event bindings, aliases, canonical titles, source authority, redirects, or publication state.

## v1.13.2.2 change

`tct_engine/story_registry.py` now performs deterministic write-time compaction of unified-incident candidate evidence across the entire persisted registry, including old records:

- normal retention: newest 8 unique evidence rows per story;
- pressure threshold: if the serialized registry remains above 45 MiB, retain newest 4 rows per story;
- emergency tier: if it still remains above the 50 MiB hard ceiling, retain newest 2 rows per story before failing;
- exact duplicate evidence is removed;
- all authoritative identity and publication fields are untouched;
- atomic write and 50 MiB hard ceiling remain enforced.

New evidence appended during generation is also bounded at the normal retention limit so the same accumulation cannot immediately recur.

## Cumulative reliability fixes retained

This overlay also contains v1.13.2.0/v1.13.2.1 changes:

- fragmented unified-incident candidates are advisory-only and cannot abort publication by themselves;
- county membership uses source authority instead of generated copy;
- legacy archive county authority is preserved conservatively;
- archive-to-live and canonical rebinding preserve county/source provenance;
- final live county enforcement repairs/quarantines recoverable placements before hard validation;
- Business & Development eligibility is enforced;
- FDOT Aug. 7-14 custom traffic article remains included in `custom_articles.json`.

## Validation

- Full workflow-equivalent pytest boundary: 782 passed, 0 failed.
- Registry compaction regressions: 6 passed, 0 failed.
- Near-ceiling reproduction: synthetic registry inflated to 52.72 MiB successfully compacted and atomically wrote at 33.89 MiB.
- The reproduction retained 2,316 stories, 3,425 event-to-story bindings, and 198 aliases.
- No production data files, generated HTML, caches, archive, or registry file are included in this overlay.
