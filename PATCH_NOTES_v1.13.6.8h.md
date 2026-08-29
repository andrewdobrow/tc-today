# v1.13.6.8h — Publication Membership Landing Page

## Purpose
Replace the compact card-style `/subscribe.html` presentation with a full publication-grade membership landing page while preserving the existing Stripe checkout, entitlement, sign-in, and pricing mechanics.

## Changes
- Full editorial landing-page hierarchy instead of a single promotional card.
- Publication hero with direct $1 introductory offer and membership value proposition.
- Expanded three-part membership value section.
- Equal monthly and annual plan presentation with existing checkout buttons and prices.
- Dynamic “Don’t miss stories like these” showcase populated from current `data.json` top stories and resolved to article URLs through `archive.json`.
- Reader-support section explaining what membership funds.
- Membership FAQ and final conversion CTA.
- Publication-style footer and responsive mobile layouts.
- No Stripe, Supabase, entitlement, or pricing-logic changes.
