# v1.13.6.7b — Hometown News Emergency Source Retirement

## Why this hotfix exists

Hometown News Treasure Coast has repeatedly surfaced old local stories with fresh-looking publication timestamps. On August 22, this produced multiple avoidable TCT republications, including:

- the Martin County $600,000 gold-bar scam that TCT had already covered on August 13; and
- the Indian River County Attainable Housing Trust story, whose underlying reporting was substantially older than the August 22 feed appearance.

The source remains useful historically, but its live publication timestamp cannot be trusted enough for automated ingestion. The immediate production requirement is therefore to stop accepting new Hometown News material before it can affect story selection, freshness, title dedupe, identity, or publication.

## Changes

### 1. Hometown News is excluded at ingestion

`hometownnewstc.com` is now an explicit excluded live source.

The exclusion recognizes:

- direct `hometownnewstc.com` article URLs;
- Google News source metadata identifying Hometown News; and
- Google News title suffixes identifying Hometown News when source metadata is incomplete.

The check runs **before title deduplication**. A stale Hometown item therefore cannot consume a headline key and accidentally block a legitimate later item with the same title.

### 2. Google News full-text recovery is disabled

Hometown News was removed from `TRUSTED_AGGREGATOR_PUBLISHERS`. A Google News wrapper attributed to Hometown is rejected rather than resolved back to the publisher page.

### 3. Full-text source status is removed

`hometownnewstc.com` was removed from `FULL_TEXT_DOMAINS` so it cannot re-enter through the normal open-source enrichment path.

### 4. Shared content/image banks also exclude Hometown

The same source-policy check is applied while building shared RSS content and image banks. This prevents a retired Hometown item from indirectly supplying article content or imagery to a newly generated story.

## What is intentionally unchanged

- Historical TCT articles sourced from Hometown News are not deleted.
- Existing story-registry identity and provenance records are not rewritten.
- No duplicate-matching threshold is weakened.
- No Sonnet model or prompt behavior changes.
- Other publishers are unaffected.

This is an ingestion/source-integrity hotfix, not a substitute for the separate persistent-story identity work exposed by the $600K scam and Herman Nettles duplicates.

## Permanent regressions

`tests/test_hometown_source_retirement.py` verifies that:

- Hometown is absent from live full-text and Google News recovery allowlists;
- a direct Hometown URL is rejected;
- a Google News Hometown wrapper is rejected;
- the exclusion happens before title dedupe, allowing a legitimate same-headline source to survive; and
- merely mentioning the words `Hometown News` in ordinary headline text does not trigger the source block without publisher identity.

## Local validation

- Hometown retirement + trusted-source recovery focused suite: **8 passed**.
- Package validation: **38 modules / 119 public exports**.
- `scripts/generate.py` syntax compilation: **PASS**.

The full workflow-equivalent suite should still be run through **Test Editorial Engine** after applying the overlay, using the repository's normal GitHub Actions dependency environment.
