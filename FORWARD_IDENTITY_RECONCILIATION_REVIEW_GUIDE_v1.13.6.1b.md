# v1.13.6.1b production review

After applying this overlay, run **Update Treasure Coast Today**.

Expected behavior if a generated placement has no current persistent story ID:

1. `write_archives()` logs `FORWARD IDENTITY HOLD` and does not authorize a forward publication write.
2. Live publication reconciliation must not accept an archive row without `editorial_story_id` as a valid receipt for that current placement.
3. The placement is removed or replaced by verified archive recovery content.
4. `data/forward-live-identity-contract.json` passes with `violation_count: 0`.
5. The run proceeds beyond forward identity validation to the remaining final contracts and deployment steps.

Production regression fixed by this release:

`17 arrested in Martin County cocaine trafficking ring... (forward_published_article_missing_story_id)`
