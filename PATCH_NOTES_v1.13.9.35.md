# TCT v1.13.9.35 — Legacy AdSense Removal

## Purpose
Final Mediavine launch cleanup. Remove TCT's retired Google AdSense integration before Mediavine ads are enabled.

## Changes
- Removes the `google-adsense-account` meta tag from all active HTML generator sources.
- Adds a sitewide retained-page cleanup contract to `scripts/generate.py`.
- On the next normal Production/Update run, the cleanup removes:
  - legacy `google-adsense-account` meta tags;
  - legacy `pagead2.googlesyndication.com/pagead/js/adsbygoogle.js` script tags.
- The cleanup runs before the Mediavine loader normalization and fails closed if either legacy AdSense marker survives.
- Google Analytics / Google Tag Manager markup is untouched.
- Mediavine markup, `mv-leader`, `mv-no-ads`, membership/paywall behavior, and the static-sidebar changes are untouched.

## Archive verification
Dry-run normalization against the current repository HTML found:
- 1,869 HTML pages scanned;
- 1,489 pages requiring cleanup;
- 1,478 stale `google-adsense-account` occurrences;
- 11 legacy AdSense script occurrences;
- 0 AdSense markers remaining after normalization.

## Tests
The same pytest selection used by the GitHub editorial workflow was run in two chunks because of the local command timeout:
- chunk 1: 672 passed;
- chunk 2: 679 passed;
- total: **1,351 passed, 0 failed**.

## Deployment
Apply this overlay on top of v1.13.9.34, run Test Editorial Engine, then run Production/Update. The Production/Update run is what rewrites retained HTML and removes the legacy AdSense markup from the live archive.
