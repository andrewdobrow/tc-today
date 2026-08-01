# TCT v1.12.2.5 — Inline Newsletter Module Border

## Problem

The Kit inline newsletter form used the correct column width and spacing, but its white wrapper had no border or module shadow. Against the white page panels, the signup could visually blend into the surrounding layout instead of reading as a distinct TCT module.

## Change

The shared `.newsletter-inline-slot` wrapper now uses the same presentation treatment as the homepage hero and Latest News rail:

- `1px solid #e6e8e4` module border;
- existing rounded clipping;
- the shared `--tct-shadow` value;
- unchanged Kit form internals, spacing, placement, UID, and responsive behavior.

The rule applies to both category-hero and article inline newsletter placements.

## Scope

This is a presentation-only change. It does not alter newsletter loading, the desktop sticky bar, the mobile modal, semantic duplicate adjudication, story identity, article generation, or canonical publication behavior.
