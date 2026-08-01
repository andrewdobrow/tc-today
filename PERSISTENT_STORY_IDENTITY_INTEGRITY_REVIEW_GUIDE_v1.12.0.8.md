# Persistent Story Identity Integrity Review Guide — v1.12.0.8

## Required reports

Review:

- `data/persistent-story-identity-integrity.json`
- `data/event-identity-authority.json`
- `data/cross-source-update-identity.json`
- `data/editorial_story_registry.json`
- `archive.json`
- the complete production workflow log

## Pass conditions

`persistent-story-identity-integrity.json` must show:

- `passed: true`
- `active_contaminated_count: 0`
- `broad_event_mapping_count: 0`
- `broad_story_write_authority_count: 0`
- `archive_quarantine_reference_count: 0`
- `circular_story_id_authorization_count: 0`
- `violation_count: 0`

The event-identity authority reports must continue to show zero unauthorized destructive actions.

## Manual page verification

Confirm these pages remain separate:

1. `2026-07-20-family-files-wrongful-death-lawsuit-after-6-year-old-dies-at-urban-air-adventure`
2. `2026-07-29-man-crashes-suv-into-port-st-lucie-liquor-store-charged-with-dui`
3. `2026-07-31-woman-86-dies-in-port-st-lucie-crash-after-failing-to-yield-at-intersection`

Each must have a different `editorial_story_id`. The July 29 page must contain the liquor-store DUI story, and the July 31 page must contain the fatal intersection crash.

## Expected behavior

- A persistent story ID may retrieve a candidate but cannot bind a permalink by itself.
- Exact normalized source identity may update the existing permalink.
- A independently verified structured incident or hard composite may update the existing permalink.
- Broad crash/fire keys never own a persistent story.
- When a story is quarantined, its articles remain public but lose that unsafe story-ID binding until independently re-identified.
