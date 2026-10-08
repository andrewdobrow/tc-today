# TCT v1.13.9.99 — Packard sponsored article current-state integration

## Purpose
Refreshes the previously prepared Packard Roofing sponsored-article overlay against the current TCT generator instead of deploying the older v1.13.9.89 generator snapshot.

## Current-state base preserved
`scripts/generate.py` in this overlay is based on the current v1.13.9.98 generator and therefore preserves the intervening production changes already present there, including the exact Oct. 7 polling duplicate redirect repair and the MARTY/source-absence-language guard. It does not restore the broader v1.13.9.96 polling identity experiment.

## Packard article
Adds the approved custom article:
- Headline: `Three generations later, Packard Roofing remains rooted on the Treasure Coast`
- Explicit permalink: `2026-10-04-three-generations-later-packard-roofing-remains-rooted-on-the-treasure-coast`
- Category: Business & Development
- Hero/social image: `https://treasurecoast.today/images/packard1.jpg`
- Carousel order: `packard1.jpg`, `packard2.jpg`, `packard3.jpg`, `packard4.jpg`
- Carousel includes arrows, dots, counter, keyboard navigation and touch swipe; no autoplay.
- `force_hero` remains false.
- Existing `publish_on: 2026-10-04` is preserved. Because that date has passed, the queue item is eligible immediately.

## Final sponsorship presentation
Uses the later cleaned-up sponsorship treatment rather than the more repetitive original v1.13.9.89 presentation.

Visible disclosure is limited to exactly two placements:
1. Top: `Sponsored by Packard Roofing & Waterproofing`
2. Bottom: `This article was produced in partnership with Packard Roofing & Waterproofing.`

Removed from the old v1.13.9.89 presentation:
- separate Sponsored badge;
- disclosure box under the headline;
- `Sponsored content` heading;
- repeated advertiser boilerplate.

Advertiser links retain:
`rel="sponsored nofollow noopener noreferrer external"`

Schema.org sponsor metadata remains present but is not a visible disclosure.

## Current custom queue preserved
`custom_articles.json` contains all current custom entries rather than the old v1.13.9.89 two-item snapshot:
1. Existing FDOT Treasure Coast traffic report.
2. St. Lucie Precincts 39/52 polling-place article using `https://treasurecoast.today/images/early-voting.webp`.
3. Packard Roofing sponsored article.

No current custom article is overwritten or removed.

## Test alignment
The existing St. Lucie custom-article test still expected the temporary `og-st_lucie.png` placeholder from v1.13.9.94 even though v1.13.9.95 changed the production image to `early-voting.webp`. This overlay updates that stale assertion to the current production image.

The Packard regression test verifies the current queue, scheduled-publication helper, four-image carousel, exactly two visible sponsorship disclosures, sponsored link attributes, and unchanged presentation for ordinary nonsponsored articles.

## Validation
- Packard/current-queue feature tests: 5 passed.
- Broader custom/canonical/redirect/copydesk integration selection: 103 passed, 0 failed.
- Direct `load_custom_articles()` current-queue check: 3 articles loaded successfully; Packard normalized with 4 carousel images.
- `scripts/generate.py` compiles successfully.
