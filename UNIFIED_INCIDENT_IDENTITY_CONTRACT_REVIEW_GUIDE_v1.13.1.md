# Unified Incident Identity Contract Review Guide — v1.13.1

## Required workflow

1. Run **Test Editorial Engine**.
2. Confirm package validation and the complete repository pytest suite pass.
3. Run **Update Treasure Coast Today**.
4. Review the workflow log and reports below before starting another increment.

## Required reports

- `data/editorial_story_registry.json`
- `data/editorial_observability.json`
- `data/persistent-story-identity-integrity.json`
- `data/story-regression-report.json`
- `data/canonical-redirects.json`
- `archive.json`
- `_redirects`

## Acceptance criteria

- Persistent-story identity integrity passes.
- `remaining_unified_incident_groups` is `0`.
- `fragmented_unified_incident_count` is `0`.
- The August 5 road-rage URL redirects to the August 4 canonical URL.
- Only the August 4 road-rage article remains in `archive.json` and live placements.
- All known road-rage fragments resolve through aliases to `story_002076`.
- The Spokane wildfire article does not share Geoffrey Lang's story ID.
- Generic or empty fact overlap cannot authorize a story attachment.
- Shared city/event-family wording without distinctive incident continuity remains
  separate.
- Verified same-incident headline drift reuses the established event canonical and
  cannot return `PUBLISH_NEW`.
- Crash closure/reopening follow-ups remain grouped.
- A fourth arrest is treated as new material information.
- Re-running registry repair makes no additional changes and quarantines no repaired
  unified incident.

The first production run may report registry health as `repaired` because historical
fragments are consolidated. The following clean run should report `clean`.
