# TCT v1.13.5.6 — Deterministic Fresh Top Stories

This increment fixes the homepage **Top Stories** surface selecting stale and archived stories ahead of newer reporting.

## Root cause

The homepage was sorting the entire enriched card pool by `urgency_score` and then sending that pool to `global_rank()`. That model prompt treated local impact as the primary signal and recency only as a secondary signal/tiebreaker. It also had no hard age ceiling and no output-size cap. Archive-recovered cards could therefore remain eligible, and the model commonly returned nearly every non-duplicate candidate as `data-topnews="true"`.

As a result, a surface labeled **Top Stories** could contain three-day-old stories and even much older archive recovery while newer Aug. 8–9 reporting existed.

## New contract

Top Stories is now deterministic and deliberately small:

- Maximum **12** stories.
- Normal stories must be **48 hours old or newer**.
- Exceptionally urgent stories (`urgency_score >= 8`) may survive only to **60 hours**.
- Nothing older than **60 hours** can enter Top Stories unless an editor explicitly pins it.
- Transient alerts/closures and routine sports recaps expire from Top Stories after **24 hours**.
- There is **no minimum-card stale backfill**. A quiet cycle shows fewer Top Stories instead of filling the section with old articles.
- Routine `lastmod` changes cannot refresh an old story. The selector uses the canonical TCT `first_published` receipt when available.
- A validated material update (`meaningful_update_validated` + `last_meaningful_update_at`) can legitimately make an older canonical current again.
- Urgency and freshness are combined deterministically; recency now has enough weight for a new medium-urgency story to outrank an older routine story.
- Explicit editor `pin_position` remains a manual override.

## Observability

Each production run writes:

`data/top-stories-ranking-report.json`

The report records every selected story's age, urgency score, ranking score and timestamp basis, plus exclusions such as `older_than_60_hours`, `expired_transient_story`, and `routine_sports_recap_older_than_24_hours`.

## Not changed

- Latest News remains strict reverse publication chronology.
- Category filters still retain the wider card pool.
- Older/archive sections are unchanged.
- Membership, paywall, Kit, Stripe, Supabase, duplicate identity and stale-source publication guards are unchanged.
