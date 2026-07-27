# TCT v1.11.5.3 — Compact Auto-Sized Product Media

## Problem

The v1.11.5.1 image viewport bounded the outer media block, but it still forced each detailed product `<img>` element to `width:100%` and `height:100%`. On mobile this preserved a large full-width image region and did not materially improve unusually tall or wide product artwork.

## Fix

- Changes detailed product images to automatic intrinsic dimensions.
- Limits the actual image with `max-width:100%` and `max-height:100%`.
- Centers the image inside a compact fixed viewport.
- Uses a 220 × 190 pixel viewport on mobile.
- Uses a 280 × 240 pixel viewport on desktop.
- Keeps `overflow:hidden`, `object-fit:contain`, layout containment and card width bounds.
- Leaves Quick Picks unchanged.
- Advances the product-guide template version to `1.7-compact-auto-sized-product-media`, forcing existing guides to regenerate once.

## Browser validation

A Chromium mobile smoke test at a 390-pixel viewport used deliberately extreme source images:

- 240 × 1600 portrait image rendered at 26 × 170 pixels.
- 1600 × 240 landscape image rendered at 200 × 30 pixels.
- 800 × 800 square image rendered at 170 × 170 pixels.
- Every media viewport remained exactly 220 × 190 pixels.
- No product card developed horizontal overflow.

## Production behavior

This patch changes only product-guide presentation and release metadata. It does not modify product data, affiliate URLs, custom article identity, story grouping, ranking, activation or publication gates.
