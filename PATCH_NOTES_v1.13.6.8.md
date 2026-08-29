# TCT v1.13.6.8 — $1 First-Month Membership Offer

## Goal
Replace the public 7-day free trial with a paid introductory monthly offer:

- Monthly: **$1 today for the first month**, then **$4.99/month**.
- Annual: **$49/year** with no introductory coupon and no free trial.
- Existing subscribers and already-trialing subscribers are not modified.

## Stripe checkout
`supabase/functions/create-checkout/index.ts` now:

- removes `trial_period_days` from new subscriptions;
- applies Stripe coupon `z039dZCN` only when `plan === 'monthly'`;
- leaves the annual plan undiscounted at its existing annual Stripe price;
- records `introductory_offer` metadata on the Checkout Session and Subscription.

The coupon may be overridden with `STRIPE_MONTHLY_INTRO_COUPON`; the production default is `z039dZCN`.

`checkout-complete` remains backward-compatible with old zero-due trial Checkout Sessions and now returns the selected plan so the browser can show accurate monthly/annual success copy.

## Customer-facing copy
The subscribe page, article paywall source, site header, homepage membership card and membership footer now lead with the $1 first-month offer. Monthly is the highlighted plan; annual remains available at $49/year.

Membership asset cache version: `1.13.6.8`.

## Retained pages
The generator's site-chrome normalization now migrates old retained `Start free trial` footer CTAs to the $1 offer. The normal membership paywall preparation stage rehydrates and rewrites already-paywalled article pages from the protected-content snapshot, so existing article paywalls receive the new offer during the next Generate News run without exposing protected article bodies.

## Compatibility
`trialing` remains an entitled Stripe status. This is deliberate so subscribers who began the previous 7-day trial before this release retain access through the end of that trial.

## Validation
- Membership-focused regression tests: 50 passed.
- Production CI test set before the final footer-only regression: 1,020 passed / 0 failed.
- Added footer migration regression: passed, yielding 1,021 validated tests across the same source state.
- Existing warnings: 41 `datetime.utcnow()` deprecation warnings.
- Package validation: 38 modules / 122 public exports.
