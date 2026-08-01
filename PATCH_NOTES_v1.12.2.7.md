# TCT v1.12.2.7 — RSS and Social Image Authority

## Problem

The RSS feed treated `image_url` as though it always represented the story's real source image. In production that field can contain three different classes of image:

- a verified image pulled from the reporting source;
- a reusable TCT editorial photograph used only to keep an article page from appearing text-only;
- a branded category OG graphic.

Because the RSS renderer emitted whatever happened to be in `image_url`, Nextdoor sometimes received a real source image, sometimes a reusable editorial placeholder, and sometimes no explicit RSS image at all. When no image was present, the importer could scrape the article's Open Graph metadata instead, producing another inconsistent path.

Article Open Graph metadata had a separate publisher-domain allowlist. A legitimate source image hosted on a publisher CDN such as `kubrick.htvapps.com` could therefore appear inside the article while the social preview fell back to the category graphic.

## Change

RSS, Open Graph, Twitter cards, structured article data, and other social syndication now share one authoritative image resolver:

1. Use the verified real source image attached to the exact article, regardless of which publisher CDN hosts it.
2. Otherwise use the green branded category OG image.

The resolver explicitly excludes:

- `images/editorial/*` reusable article photographs;
- legacy `images/fallback/*` assets;
- generic or wrong-category branded OG images;
- rejected publisher logos, tracking pixels, and other invalid source imagery.

Every RSS item now contains an explicit `media:content` image. Nextdoor no longer needs to infer an image by scraping the article page. A production contract writes `data/rss-social-image-contract.json` and stops deployment if an item is missing an image, leaks an article placeholder, or disagrees with the authoritative resolver.

## Expected behavior

- Source image available: RSS and article social metadata use that source image.
- Source image unavailable or rejected: RSS and article social metadata use the matching green category OG card.
- The image displayed inside the article may still use a reusable editorial fallback, but that image never appears in RSS or social metadata.
