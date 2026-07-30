# TCT v1.12.0.5 — Canonical Hero Freshness Integrity

## Problem

A newly discovered source could be selected as the homepage hero and later rebound to an older canonical TCT article. The incoming source timestamp survived the rebind, allowing an unchanged 10-day-old article to appear fresh.

## Fix

- Canonical archive timestamps now replace source timestamps whenever a live placement is rebound.
- Homepage freshness ignores `lastmod`, redirect work, image repairs, cache recovery, and repeated source coverage.
- Only `first_published` or a validated `last_meaningful_update_at` can qualify a canonical article as fresh.
- A meaningful update timestamp is written only when the update changed the article and passed both original-context and novelty checks.
- After archive writing and final canonical resolution, the homepage hero is revalidated and deterministically replaced when a fresh canonical alternative exists.
- The build fails if a stale final hero remains while any fresh canonical candidate is available.

## New report

`data/canonical-hero-freshness-contract.json`

## Permanent regression

The July 20 Stuart animal-hoarding article may not become hero from a July 30 source repeat unless a validated contextual update is actually published.
