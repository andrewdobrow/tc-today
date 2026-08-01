# TCT v1.12.2.8 — RSS Image Authority Persistence

## Production failure

The v1.12.2.7 production contract stopped the build with four image-policy violations even though the RSS renderer had selected verified source images correctly.

The split occurred because RSS can enrich an archive article from its exact live hero/card object. That live object may contain a newly recovered publisher image while the older archive row still contains an article-only editorial placeholder or no image. The feed therefore emitted the source image, but the validator recomputed its expectation from the stale archive row and expected a category OG card.

This also meant a publisher image recovered during one run was not guaranteed to remain available to RSS on a later run after the article left the live grid.

## Correction

When the canonical RSS renderer selects a verified source image, it now persists that URL into the exact archive row as `source_image_url` before contract validation. The visible article `image_url` is not replaced, so an editorial fallback can remain inside the page while source imagery stays authoritative for syndication.

The renderer also synchronizes the existing article page's:

- `og:image`;
- `twitter:image`;
- NewsArticle structured-data image.

All three now match the explicit RSS `media:content` image. The visible article-body image is never changed by this synchronization.

The runtime contract additionally verifies that each article's Open Graph image agrees with RSS and reports how many source images were durably persisted.
