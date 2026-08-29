# TCT v1.13.6.8b — Compact Header Subscribe CTA

This narrow presentation patch removes the recurring renewal-price phrase from the site header Subscribe CTA.

## Header CTA
Before:
- Subscribe
- Limited time · $1 first month · then $4.99/mo

After:
- Subscribe
- Limited time · $1 first month

The header aria-label is also shortened to `Subscribe to Treasure Coast Today — $1 first month`.

## Unchanged disclosures
The normal $4.99/month renewal disclosure remains on the subscribe page, article paywall, footer membership CTA, and Stripe Checkout. This patch changes no pricing, coupon, billing, entitlement, or Stripe behavior.

## Generator persistence
`scripts/generate.py` and the mirrored root `generate.py` use the compact header CTA, so regenerated/retained site chrome will not restore the removed renewal phrase.

## Validation
Focused membership/header regressions: 25 passed, 0 failed.
