# Authoritative Custom Archive Identity Review Guide — v1.12.0.3

## Expected production behavior

During archive identity backfill, older custom articles without `editorial_story_id` should receive deterministic IDs beginning with `custom:`.

Review `data/archive-identity-backfill.json` and confirm:

- `custom_backfilled` is greater than zero on the first repaired run.
- The Stuart animal-hoarding canonical has `identity_origin` equal to `authoritative_custom_archive_backfill`.
- Recurring custom editions have different story IDs when their canonical slugs differ.
- The final log reaches `Forward live identity contract PASSED`.
- The summer reading product guide remains archived and renders normally.

## Regression requirements

The tests prove that:

1. A legacy authoritative custom page receives a stable story ID.
2. Running the migration again preserves the same ID.
3. Two recurring custom editions never collapse into one ID.
4. The exact production hoarding placement passes the forward-live identity contract after backfill.
5. Generated and legacy non-custom archive rules remain unchanged.
