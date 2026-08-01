# v1.12.0.8.3 — Explicit Custom Slug Integrity

## Production failure addressed

The manually supplied traffic-report permalink was 84 characters long and ended in the edition marker `aug-2-7`. The generic generated-headline `slugify()` helper has an intentional 80-character limit. The custom publication path incorrectly reused that helper, silently publishing the requested permalink as a truncated slug ending in `-aug`.

The recurring custom-edition identity contract then correctly rejected the live placement because the published URL no longer contained the article's explicit `Aug. 2-7` edition marker. The run reached the final live identity gate and failed with `recurring_custom_edition_slug_mismatch`.

## Root cause

Generated slugs and editor-supplied slugs have different contracts:

- generated headline slugs may be shortened deterministically;
- an explicit custom slug is a publication instruction and must not be silently altered.

The engine treated both through the same 80-character normalizer. This was a publication-layer defect, not an event-identity failure.

## Changes

- Adds a dedicated custom-slug normalizer that does not inherit the generic 80-character clipping rule.
- Preserves the complete editor-supplied traffic-report permalink, including `aug-2-7`.
- Validates explicit custom slugs against a documented 180-character ceiling and fails immediately instead of silently truncating.
- Uses the same custom-slug normalization for queue collision checks, archive matching, custom target resolution, and recurring-edition validation.
- Recognizes abbreviated month labels with optional punctuation, including `Aug. 2-7`, as explicit edition markers.
- Keeps the generic 80-character rule unchanged for automatically generated article slugs.

## Exact regression

The production traffic payload now publishes to:

`2026-07-31-treasure-coast-traffic-report-i-95-ramp-and-road-closures-planned-aug-2-7`

The suffix is preserved, the archive entry reports `custom_edition_key: aug-2-7`, and the final forward live identity contract accepts the placement.
