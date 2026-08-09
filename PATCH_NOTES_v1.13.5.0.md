# TCT v1.13.5.0 — Membership Launch Candidate

This increment turns the dark-launched membership work into a launch-ready reader experience without enabling it by default.

## Reader-facing launch design
- Replaces the header Advertise CTA only when `TCT_MEMBERSHIP_UI_ENABLED=true`.
- Desktop CTA is coral and shows `SUBSCRIBE` with `$4.99/mo · $49/yr` beneath it.
- Pricing collapses before the desktop nav can become cramped; mobile shows a compact Subscribe button only.
- Adds a quiet `Sign in` link beside the desktop Subscribe CTA.
- Applies launch header chrome to retained/static pages as well as newly rendered pages so the site cannot launch with mixed Advertise/Subscribe headers.
- Homepage membership promo card uses the same coral/white membership visual system.

## Subscription landing page
- `/subscribe.html` is now the real membership landing page.
- Keeps plan selection ahead of authentication: no registration gate or password creation before payment.
- Annual and monthly cards remain balanced with annual marked Best Value.
- Adds concise recurring-billing disclosure and passwordless existing-member sign-in.
- Keeps sandbox/live-validation banners while the membership UI is dark.

## Paywall and SEO
- Keeps paragraph one plus a sentence-aware excerpt of paragraph two public.
- Protected article remainder remains absent from public HTML and is delivered only after server-side entitlement verification.
- Paid-content structured data now points to the protected-content placeholder rather than the paywall UI itself.
- Adds automatic-renewal/cancellation disclosure to the article paywall.
- `/subscribe.html` becomes indexable only when the launch switch is enabled.
- Adds `/subscribe.html` to the sitemap only when membership is live.

## Live-mode safety
- Adds `TCT_STRIPE_MODE` (`test` or `live`) as an explicit deployment safety control.
- Browser config refuses to enable the public membership UI unless `TCT_STRIPE_MODE=live`.
- Edge Functions verify that the configured Stripe secret key matches the declared mode.
- Webhooks and Checkout completion reject cross-mode events/sessions.
- Subscriptions now store `stripe_livemode`; live entitlement checks cannot be satisfied by earlier sandbox subscriptions.
- The engineering membership-test page cannot start Checkout after Stripe is switched to live.

## Funding/privacy consistency
- Launch-state ownership/editorial copy recognizes reader memberships without giving members editorial influence.
- Privacy policy now covers Stripe, Supabase, Resend, membership account data and subscription entitlement data.

## Database migration
Apply:
`supabase/migrations/202608090003_membership_live_mode.sql`

This adds `subscriptions.stripe_livemode` and a mode-aware entitlement index. Existing sandbox rows correctly default to `false`.

## Launch switch remains off
This overlay does **not** change the repository variable `TCT_MEMBERSHIP_UI_ENABLED`. Keep it `false` until live Stripe prices, webhook, secrets, portal and one real end-to-end purchase have been verified.
