# TCT v1.13.9.104 — Packard paywall exemption

## Purpose
Keep the Packard Roofing sponsored feature permanently outside the Treasure Coast Today membership paywall while leaving ordinary editorial and future sponsored-content policy unchanged.

Exact exempt slug:
`2026-10-04-three-generations-later-packard-roofing-remains-rooted-on-the-treasure-coast`

## Changes
- Adds one centralized exact-slug paywall exemption in `tct_engine/membership_paywall.py`.
- `scripts/prepare_membership_paywall.py` skips Packard before article splitting/protection.
- If Packard was already paywalled and a protected snapshot is available, the preparation step rehydrates the complete article, restores `isAccessibleForFree: true`, removes the paywall-only `hasPart` schema, and leaves the article fully public.
- If a previously protected Packard page cannot be safely rehydrated, the membership step fails closed rather than silently leaving advertiser-funded content paywalled.
- `scripts/sync_protected_articles.py --scan-public` also excludes the Packard slug so a fallback scan cannot re-enroll it in protected content.
- No changes to `generate.py`, `custom_articles.json`, article copy, carousel, sponsorship disclosure, deduplication, ranking, redirects, or membership pricing.

## Validation
- Packard-specific exemption tests: 4 passed.
- Existing membership/protected-content suite + Packard exemption tests: 39 passed.
- Python compilation passed for all three modified production modules and the new regression test.

## Apply
Apply on top of the current `.103` state. This patch does not replace or revert `.102` or `.103` changes.
