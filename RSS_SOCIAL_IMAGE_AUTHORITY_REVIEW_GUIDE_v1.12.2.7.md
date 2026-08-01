# RSS and Social Image Authority Review Guide — v1.12.2.7

## Apply

Apply this repository-root overlay on top of **v1.12.2.6**.

## Verify the feed

First confirm that `data/rss-social-image-contract.json` reports `status: passed`, then open `feed.xml` and inspect a mix of stories:

- A story with a verified publisher image should include that exact URL in `media:content`.
- A story whose article page uses an image under `/images/editorial/` should instead include its green category OG image in `media:content`.
- Every item should contain one `media:content` element.
- No RSS image URL should contain `/images/editorial/` or `/images/fallback/`.

## Verify article metadata

Inspect the HTML source of the same articles:

- `og:image`, `twitter:image`, and the structured-data image should match the RSS image policy.
- A legitimate external publisher CDN is allowed; the old fixed domain allowlist is gone.
- The visible article hero image may remain a reusable editorial fallback. That is intentional and independent from social syndication.

## Nextdoor

Nextdoor may cache an already-imported preview. Use newly published items to verify the policy immediately. Existing cached posts may retain their original image even after the feed is corrected.

## Regression scope

The release includes tests proving that:

- a verified source image on an unlisted publisher CDN remains authoritative;
- managed editorial placeholders are replaced by the category OG card for RSS/social;
- missing and generic-branded images resolve to the correct category OG card;
- every RSS item receives an explicit image;
- article Open Graph metadata uses the same resolver as RSS.
