# Explicit Custom Slug Integrity Review Guide — v1.12.0.8.3

## Required production result

The workflow must complete without `recurring_custom_edition_slug_mismatch`. The traffic report must be bound to the complete requested permalink:

`2026-07-31-treasure-coast-traffic-report-i-95-ramp-and-road-closures-planned-aug-2-7`

It must not be shortened to a slug ending in `-aug`.

## Log checks

Confirm that the custom publication line includes the complete suffix:

`Custom publication directly bound ... planned-aug-2-7`

The final contracts must report:

- Persistent story identity integrity: passed
- Forward live identity contract: passed
- Live permalink integrity: passed
- Story regression production gate: passed

## Archive checks

The current traffic archive record should contain:

- the exact traffic headline;
- the full requested slug;
- `custom_series_key: treasure-coast-traffic-report`;
- `custom_edition_key: aug-2-7`;
- no identity quarantine reason.

Previous weekly traffic editions remain separate archived pages and are not redirected to the current edition.
