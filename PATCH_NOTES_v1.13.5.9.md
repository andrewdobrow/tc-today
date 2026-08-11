# TCT v1.13.5.9 — 7-day membership free trial

## What changed

- Stripe Checkout now starts both monthly and annual memberships with a 7-day free trial.
- Checkout explicitly collects a payment method up front so the selected subscription can begin automatically after the trial unless canceled.
- Existing `trialing` entitlement support is retained, so trial members receive full protected-article access immediately.
- Checkout completion copy now describes a free trial rather than an immediate payment.
- The article paywall, subscribe page, homepage membership card, header CTA subtext and footer CTA now advertise the 7-day trial consistently.
- The paywall/subscribe hero visually strikes through `$5/month` in a lighter tone and emphasizes `FREE for 1 week`, while separately disclosing the actual post-trial monthly and annual prices.
- Membership assets are cache-busted to `v1.13.5.9`.

## Billing behavior

New Checkout subscriptions receive `trial_period_days: 7`. Stripe Checkout is told to use `payment_method_collection: always`. Existing subscriptions are not modified.

## Safety

The protected-content model, Supabase entitlement tables, webhook signature verification, Stripe live/test isolation, canonical publishing, editorial identity and ranking logic are unchanged.
