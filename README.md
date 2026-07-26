# TCT Hurricane Product Guide Content Package

## Article

**Hurricane Season Ready: 12 Treasure Coast Essentials to Stock Up On**

The prepared entry contains all 12 products, exact affiliate links and TCT-hosted transparent product image URLs supplied by Andrew.

## Installation

This content package assumes the product-guide renderer from TCT v1.11.0+ and the incident-lock release v1.11.1.

1. Apply `product-guide-image-containment.patch` after v1.11.1.
2. Place the generated hero image at:
   `images/hurricane-season-ready-treasure-coast-essentials.png`
3. Preview the JSON merge:
   `python scripts/install_hurricane_product_guide.py --target custom_articles.json --dry-run`
4. Install it:
   `python scripts/install_hurricane_product_guide.py --target custom_articles.json`
5. Run **Test Editorial Engine**, then production.

The installer only replaces an article with the exact headline `Hurricane Season Ready: 12 Treasure Coast Essentials to Stock Up On`. All other custom articles are preserved.

## Image containment

The patch changes product-image boxes to fixed-height, overflow-hidden containers with padding. Product PNGs use `max-width:100%`, `max-height:100%`, `width:auto`, `height:auto`, `object-fit:contain`, and centered positioning. This prevents transparent product images with unusual dimensions from stretching cards or overflowing on desktop or mobile.

## Files

- `content/hurricane-season-ready-product-guide.json` — publication-ready custom article entry
- `scripts/install_hurricane_product_guide.py` — exact-headline merge installer
- `preview/hurricane-season-ready-preview.html` — local visual preview
- `product-guide-image-containment.patch` — renderer hardening against image overflow
- `research-notes.md` — key claims and source notes
