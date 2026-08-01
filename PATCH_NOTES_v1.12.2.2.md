# TCT v1.12.2.2 — Semantic Candidate Recall Expansion

## Summary

v1.12.2.1 corrected the hard veto caused by conflicting generated event keys, but one confirmed duplicate still fell below the single fuzzy-score threshold:

- `2026-07-29-port-st-lucie-officer-resigned-after-leaving-scene-of-suspected-suicide-without`
- `2026-08-01-port-st-lucie-officer-resigns-after-allegations-he-left-scene-where-man-later-di`

The two headlines describe the same Port St. Lucie officer resignation and suspected-suicide scene, but the publishers framed the incident differently. Their aggregate fuzzy score was too low even though they shared the distinctive bundle of Port St. Lucie, officer, resign, leave, scene, and suicide. Both records also carried different generated `unknown-event-*` keys.

## Correction

Candidate retrieval now uses two structured-conflict override tiers:

1. **Strong headline similarity**
   - headline similarity at least `0.74`
   - at least six shared canonical headline tokens

2. **Distinctive token overlap**
   - headline similarity at least `0.56`
   - at least eight shared canonical headline tokens

The second tier is designed for the same incident being described from materially different narrative angles. It remains candidate-only: Claude must still determine same-event identity, whether the newer report is a material update, and the final action.

Headline normalization now also aligns common reporting variants:

- `resigned`, `resigns`, `resigning` → `resign`
- `left`, `leaves`, `leaving` → `leave`

## Existing duplicate repair

The July 29 officer article remains the expected canonical page. If Claude confirms that the August 1 article repeats the same internal-affairs investigation and resignation without a consequential new development, the August 1 URL is removed from active surfaces and redirected to the July 29 URL.

## Diagnostics

Each admitted conflict candidate now reports:

- `structured_conflict_override`
- `structured_conflict_override_tier`
- `headline_similarity`
- `shared_token_count`
- conflicting incident or known-event keys
- final Claude decision and selected canonical slug

The gate cache version advances to `1.2`, preventing decisions from the earlier retrieval policy from being reused.

## Safety retained

- Seven-day recent-story window
- Maximum of four candidates
- No fuzzy-only merge authority
- Claude must return a validated decision at the confidence threshold
- Model failures and ambiguous responses fail closed
- Authoritative custom articles remain excluded from retroactive repair
