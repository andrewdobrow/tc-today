# v1.13.6.7h Review Guide — Fresh Follow-up Hero Preservation

## Purpose

Verify that final-pipeline alignment no longer replaces a genuinely fresh follow-up hero solely because the underlying event occurred the previous day.

## Expected natural-run evidence

For a current-day update such as Monday NWS confirmation of a Sunday tornado:

- the raw Sonnet assignment may select the fresh update as hero;
- `alignment_diagnostics.shadow.stale_hero_swap` should remain `null` unless the shared stale contract has real evidence the story is stale;
- the final shadow hero should remain the assigned hero unless a separate shared deterministic gate rejects/suppresses/canonicalizes it;
- the production and shadow stale-story decisions use the same helper.

## Crime category-fit regression remains intact

A tornado source that leaks into the Crime & Safety packet should still be rejected by Sonnet 5's topic-category-fit adjudication. This patch does not change v1.13.6.7f behavior.

## Stale re-touch control

A source with a fresh feed timestamp but only old-event language and no genuine current-day development must still be eligible for stale-hero replacement.
