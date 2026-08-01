# TCT v1.12.2.4 — Canonical Hero Archive Recovery

## Problem

The final canonical hero freshness barrier correctly found fresh canonical candidates after archive publication, but `select_front_page_hero()` searched only the active live-placement pool whenever any live placement existed. If every live placement was stale while one or more recent archive-recovery placements were fresh, reselection returned the same stale live hero and the workflow stopped with:

`Canonical hero freshness contract FAILED: final hero is stale while fresh canonical candidates exist`

## Change

Hero selection now uses a tiered freshness order:

1. fresh active live placements;
2. fresh canonical archive-recovery placements;
3. deterministic stale non-sports fallback only when neither tier contains a fresh candidate.

Archive recovery cannot displace a fresh live placement. It is considered only when the live pool has no fresh candidate, making the selector and the final freshness barrier evaluate the same eligible universe.

## Diagnostics

The workflow prints `using fresh canonical archive recovery` when this tier is activated. The front-page hero audit records `deterministic_post_canonical_archive_recovery` for final deterministic reselection.

## Scope

This patch does not change semantic duplicate adjudication, registry consolidation, article generation, canonical URLs, custom-article authority, or newsletter presentation.
