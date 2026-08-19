# v1.13.6.1e — Live category identity alignment stabilization hotfix

## Production failure addressed

The Aug. 19 production run reached the final live-category canonical gate after successfully passing forward live identity, live permalink integrity, canonical hero freshness, final image repair, and final county authority. The preceding canonicalization reported that it removed one duplicate placement and rewrote ten canonical placements, but the immediately following validator still found one duplicate/redirect-source placement.

## Root cause

`canonicalize_all_live_category_surfaces()` resolved each category hero from the full live hero object. However, when it called `_dedupe_homepage_cards_by_permalink()`, the card deduper reconstructed the hero identity from the hero permalink alone (`{}` + URL). The final validator used the full hero object again.

A current-run hero can legitimately carry durable story/incident identity in memory before every equivalent field is available from the archive row. In that case:

1. canonicalization sees the full hero identity;
2. the nested card deduper loses that live-only identity by reducing the hero to its URL;
3. an equivalent card survives;
4. the final validator restores the full hero identity and correctly fails closed.

The canonicalizer and validator were therefore applying the same policy to different identity inputs.

## Fix

- `_dedupe_homepage_cards_by_permalink()` now accepts an optional `hero_item`.
- When final surface context is active, hero identity is resolved from the full live hero object plus permalink—the same inputs used by the final validator.
- Both all-category canonicalization and final homepage dedupe pass the live hero object.
- The final live-category validator now emits category, placement, reason, identity key, href, and headline for up to ten violations before raising. This is diagnostics-only and does not weaken fail-closed behavior.

## Regression coverage

Added an exact regression where two placements share a live-only incident identity that is intentionally absent from their archive rows. The test proves URL-only hero resolution loses the identity, then verifies canonicalization removes the duplicate and the immediately following validator passes.

## Behavior intentionally unchanged

No changes to story matching, follow-up classification, story lifecycle, persistent story IDs, archive identity, redirect authority, county authority, ranking, hero freshness, image selection, membership, custom article authority, or the forward-live identity contract.
