# TCT v1.11.5.1 — Bounded Mobile Product Media

## Problem

Full product-guide cards used natural image height on mobile. Very tall or portrait-oriented product images could therefore expand the media region far beyond the intended card area, even though Quick Picks remained correctly contained.

## Fix

- Gives each full product-card image a bounded media viewport.
- Uses `object-fit: contain` so the entire product remains visible without cropping.
- Applies `overflow: hidden`, width bounds and layout containment to prevent intrinsic image dimensions from escaping the card.
- Uses a 280px media viewport on desktop and a 230px viewport at widths of 720px or less.
- Leaves Quick Picks unchanged.
- Advances the product-guide template version to `1.5-bounded-contain-product-media` so existing product guides regenerate with the corrected CSS.

## Safety

- No product URLs, affiliate links, product data or custom article queue entries are changed.
- No news ranking, story identity, follow-up detection or image-pool behavior is changed.
