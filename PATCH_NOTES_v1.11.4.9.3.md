# TCT v1.11.4.9.3 — Fallback Subject and Source Image Protection

Base: **v1.11.4.9.2**

## Problem confirmed from production

The first successful editorial-image migration reassigned 355 archive records and
created 357 new image assignments in one run. The roads pool was selected too often
because:

1. `crash`, `collision`, and `airport` were treated as high-specificity road signals.
2. Topic classification scanned up to 2,800 characters of body text, so an incidental
   reference such as “Okeechobee Road” could override a business story.
3. Homepage/card rendering could select a fallback even when the exact permanent
   article already stored a real publisher image.

## Changes

### Road pool is now infrastructure-specific

The roads pool is reserved for visible road and traffic subjects such as:

- roads and roadwork
- traffic operations
- bridges and causeways
- highways, I-95 and the Turnpike
- lanes, ramps, intersections and detours
- closures and FDOT/transportation projects

`crash`, `collision`, `airport`, and `rail` no longer trigger the roads pool by
themselves.

### Topic selection uses headline and teaser only

Full body and article text remain available for location detection, but they no longer
control topic-image selection. This prevents incidental terms in long article copy from
hijacking the fallback pool.

Expected corrected results:

- JetBlue Vero Beach–JFK cancellation → `cities/vero-beach`
- P1 Motor Club racetrack resort → real WPTV image when available; otherwise
  `topics/business-development`
- Dirt-bike crash memorial → exact city when present, otherwise
  `topics/crime-public-safety`

### Real archived source images are restored first

Before assigning a reusable fallback, live heroes and cards now check the exact archive
record by slug, persistent story ID, or exact headline. A real source image stored on the
permanent article outranks all editorial fallback images.

The match is deliberately exact; fuzzy headline matching is not used for image recovery.

### Archive migration is versioned

The full archive fallback migration now runs once per
`EDITORIAL_IMAGE_SELECTION_POLICY_VERSION`.

After policy v3 completes successfully, normal runs write a skipped migration report
instead of rescanning and reopening every historical article page. The completion marker
is committed only after all production gates pass.

## Validation

- Python compilation: passed
- Package validation: 29 modules and 98 public exports
- Focused image regressions: 17 passed
- CI-equivalent editorial suite: 348 passed
- Existing warnings: 17 `datetime.utcnow()` deprecation warnings
- `custom_articles.json`: unchanged
- Editorial image assets: unchanged

GitHub Actions and production deployment have not yet run with this overlay.
