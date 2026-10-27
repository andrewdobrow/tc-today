# TCT reader-supported transition — staged rollout (October 27, 2026)

**Not activated by this pull request.** The current production subscription/paywall model remains unchanged until an operator intentionally configures `TCT_READER_REVENUE_MODE=donation_ads` and provides a genuine Stripe Payment Link.

## What the code prepares

- Restore the full text of previously paywalled articles from the private Supabase protected-content snapshot. The process aborts if a required body is missing or malformed. Nothing from the snapshot is stored as a public JSON file; only the resulting *intentionally public* article HTML is committed.
- Stop generating new paywalls, remove login/meter/sales chrome from open-access pages, and mark Article JSON-LD `isAccessibleForFree: true`.
- Promote **Advertise** to the main desktop navigation immediately after **Events**, removing the duplicate from the desktop More dropdown. Preserve the mobile Advertise link in the hamburger navigation.
- Replace the public **Subscribe** button and homepage membership promotion with **Donate**.
- Generate `/donate.html` with a verified Stripe-hosted **choose-your-amount, one-time** Payment Link. A real link is mandatory. State clearly that TCT LLC is **for-profit** and reader support is **not tax-deductible**.
- Preserve `/subscribe.html` solely so existing paying customers can manage historical membership billing. New-purchase controls are hidden in the new mode. Preserve historic Subscription Terms and augment Privacy Policy text with donation collection and ad-use disclosures.
- Keep the existing Mediavine script **unchanged**. No invented ad slots, no duplicate loaders, no new network tracking.

## Critical tasks before launch

- **Existing Stripe subscriptions as of October 27, 2026:** 15 active monthly at $4.99, 19 active annual at $49, 1 past due monthly, 6 canceled monthly. All 34 active and the past-due subscriber should be assessed before enabling an ad-supported experience for everyone. Do not change subscription billing without the publisher's explicit migration decision.
1. **Migrate paid subscriber obligations.** Existing subscribers were promised ad-free access. Decide how to honor their paid periods (keep them ad-free in supported experiences, or cancel renewals and proactively refund unused benefits as appropriate), and communicate the change. Do **not** silently turn paying customers into ad-supported readers.
2. **Stop the creation of new subscriptions on the server side.** Existing `create-checkout` Supabase Edge Function can still sell monthly/annual memberships through direct requests; hiding the front-end buttons is **not enough**. Deploy a server-side restriction and verify no new Stripe subscription can be created before exposing the public donation site. Preserve the customer billing portal, cancellation, webhooks, and historical records.
3. **Stripe link verified:** TCT's existing active production Payment Link is `https://donate.stripe.com/4gM5kw9LWfRb7uV6P34ZG01`. Its Stripe line item uses `custom_unit_amount` on a one-time USD price, not a recurring subscription. The workflow defaults to this link; optionally override it with `TCT_DONATION_PAYMENT_LINK`. Confirm branding, receipt emails, donation language and processing fees before activation.
4. Confirm the complete protected-content snapshot can be retrieved using `TCT_SUPABASE_URL` and `TCT_CONTENT_SYNC_SECRET`. An unsuccessful snapshot **must block the launch**, not expose teasers as complete articles.
5. Test the **iOS app**, its privacy disclosures and any membership/paywall screens. The mobile app must not continue charging for full-article access that is now free on the website.
6. Ask Mediavine to assess its current sitewide loader, optimal in-content/adhesion/sidebar placement and ad-density settings, particularly for short local news stories. Do not insert unapproved or duplicate tags.
7. Review/update `subscription-terms.html`, `privacy.html`, advertiser disclosures and relevant public-facing pages. Obtain legal/accounting review as needed.
8. Run `Test Editorial Engine` before switching modes. After setting the two repository variables below, run the existing `Update` workflow and inspect the published site, canonical links, pages, SEO accessibility, redirects, newsletter links, ad display, the iPhone app, and Stripe checkout.
9. Measure pageviews per session, Google Discover/search referrals, return readers, ads RPM, donations, and advertiser inquiries for 30 days against the preceding period.

## Activation (after the above checks)

Repository Actions variables:

- `TCT_READER_REVENUE_MODE=donation_ads`
- Optional override: `TCT_DONATION_PAYMENT_LINK=https://donate.stripe.com/4gM5kw9LWfRb7uV6P34ZG01` (the current live link is already the workflow default).

Keep the existing `TCT_MEMBERSHIP_UI_ENABLED` setting until the legacy billing transition is completed, because it also controls browser membership configuration and billing tools. The new mode explicitly disables the article splitter regardless of that legacy flag.

**Never put Stripe secret keys, Supabase secrets, subscriber lists, or protected-content snapshots in a Git commit.**

## Rollback

Unset `TCT_READER_REVENUE_MODE` or set it back to `subscription`, then rerun the existing Update workflow **only after** confirming the subscription/backend/account commitments: re-enabling the old paywall will affect free readers and could require protected store resync. Keep a backup of pretransition article commits and do not reinstate charging unintentionally.
