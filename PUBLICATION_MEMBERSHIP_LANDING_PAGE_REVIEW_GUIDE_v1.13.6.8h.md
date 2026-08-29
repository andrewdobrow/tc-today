# Publication Membership Landing Page Review Guide — v1.13.6.8h

## Scope
This increment changes only the presentation and content hierarchy of `/subscribe.html` plus the landing-page CSS and related regression expectations. Stripe checkout, Supabase entitlement, sign-in, plan IDs, prices, and renewal logic are unchanged.

## Visual review
1. Open `/subscribe.html` on desktop and mobile.
2. Confirm the page reads as a full publication landing page, not one large promotional card.
3. Confirm the hero clearly states the $1 first-month offer and includes a sign-in path.
4. Confirm the value section has three editorial membership benefits.
5. Confirm monthly and annual plans are equally complete, with monthly visually primary.
6. Confirm “Don’t miss stories like these.” displays the current homepage hero and top cards with images, category labels, teaser text and article links.
7. Confirm the reader-support section, FAQ and final CTA render below the story showcase.
8. Confirm the layout collapses cleanly on mobile without horizontal overflow.

## Functional review
- Monthly button: existing `$1 first month -> $4.99/month` Stripe checkout.
- Annual button: existing `$49/year` Stripe checkout.
- Sign in: existing passwordless membership sign-in.
- Current stories: client-side read-only fetches of `/data.json` and `/archive.json`; no external service and no publication mutation.
- If story data cannot be loaded, the section falls back to a Top News link rather than failing the page.
