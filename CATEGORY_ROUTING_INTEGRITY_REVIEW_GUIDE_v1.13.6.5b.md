# Category Routing Integrity Review Guide — v1.13.6.5b

## Purpose

Verify that every topic-category source has an explicit classification, local topic sections enforce Treasure Coast locality before model generation, and Things To Do contains only genuine local attendable activities/events.

## What changed

### Classification coverage

The old global `stories[:120]` truncation is removed. Classification now processes every unique feed story in bounded 120-story batches. Existing cache hits remain free. A failed classification batch does not fall back to topic keywords; affected stories are blocked from topic-category generation.

### Local topic locality

Before category scoring/model generation, Local Government, Crime & Safety, Business & Development, Sports, and Things To Do require deterministic Treasure Coast locality. A bad model classification cannot bypass this boundary.

### Things To Do contract

Things To Do is now an enforced category contract. A source must have both:

- Treasure Coast locality; and
- a central attendable activity/event signal such as a festival, concert, fundraiser, performance, workshop, food/dining event, race/recreation event, or cultural program.

Animal-hoarding recovery, crime/public-safety, and government-action stories without an explicit attendable-event focus are rejected.

## Required production checks

1. Run **Update Treasure Coast Today** with **Run Sonnet 5 shadow model bake-off** unchecked.
2. In `Generate news`, find `Story classification:`. Confirm the log reports the number of batches and ideally `0 unclassified/blocked`.
3. Find `Processing: Things To Do...`.
4. Confirm no Palm Beach County, Delray Beach, Jupiter, Sunrise, or Martin County hoarding-recovery story appears among the selected Things To Do source headlines.
5. If no valid live event exists, archive recovery is expected and correct.
6. Review `data/category-eligibility-report.json`; Things To Do should now appear under enforced categories.
7. Only after this routing validation is clean should another Sonnet 4.5 vs Sonnet 5 bake-off be run.

## Regression guarantees

- story #121 is classified rather than silently truncated;
- a failed classification batch cannot use keyword fallback for topic categories;
- out-of-area stories cannot enter local topic beats even under a wrong classifier label;
- the exact Aug. 22 contaminated Things To Do pool is rejected before model generation;
- a genuine Fort Pierce local food festival/live-music event remains eligible;
- Things To Do cache invalidation is scoped only to Things To Do.
