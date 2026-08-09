# TCT v1.13.3.0 — Membership Backend Dark Launch I

This increment adds the first deployable membership backend while keeping all reader-facing paywall behavior disabled.

## Added
- Supabase Edge Functions for authenticated membership status, Stripe Checkout creation, and signed Stripe webhook processing.
- Server-side administrator entitlement (`profiles.is_admin`) so the owner can have permanent full access without a Stripe subscription.
- Auth-profile trigger/backfill and Stripe webhook idempotency table migration.
- Hidden, `noindex` `/membership-test.html` sandbox harness for magic-link/password auth, admin access checks, and monthly/annual Stripe sandbox checkout.
- Browser-safe membership config generation from GitHub repository variables. The writer rejects privileged Supabase keys.
- Manual-only GitHub Actions workflow for deploying Supabase Edge Functions.

## Not activated
- `TCT_MEMBERSHIP_UI_ENABLED` remains false by default.
- Existing Advertise header CTA and homepage solicitation card remain visible to readers.
- No article is truncated or paywalled.
- No protected article body is moved to Supabase yet.
- No live Stripe pricing is used.

## Next validation
1. Run the SQL migration in Supabase.
2. Mark the owner's confirmed Supabase profile as `is_admin=true`.
3. Configure GitHub's public Supabase variables and deployment token.
4. Deploy functions manually.
5. Create the Stripe sandbox webhook and save its signing secret in Supabase.
6. Test admin bypass and one sandbox subscription end-to-end on `/membership-test.html`.
