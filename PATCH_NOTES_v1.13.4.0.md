# Treasure Coast Today v1.13.4.0 — Pay-First Membership Dark Launch

This increment replaces the engineering login-first membership flow with the production subscription architecture while keeping all reader-facing membership UI dark by default.

## Reader conversion flow

- No TCT account is required before payment.
- Monthly and annual plan buttons open Stripe Checkout immediately.
- Stripe collects the subscriber email and payment details.
- A signed Stripe completion/webhook establishes or links the Supabase identity by email.
- After successful payment, TCT automatically sends a passwordless Supabase magic link through the configured Auth email provider.
- Existing members use `Already a member? Sign in` and receive the same passwordless link.
- No ordinary-reader password or registration form is presented.

## Account and entitlement

- Added authenticated Stripe Customer Portal creation for billing/cancellation management.
- Preserved the server-side `profiles.is_admin` entitlement bypass.
- Added authenticated protected-article retrieval. The browser never receives protected text unless the server verifies an administrator or an active/trialing Stripe subscription.

## Protected article architecture

- Added deterministic sentence-aware previews: paragraph 1 plus up to two sentences of paragraph 2.
- The protected remainder is removed from public HTML when membership is enabled.
- Protected article text is exported only to an out-of-repository temporary path and must sync successfully to Supabase before the workflow can commit/deploy a paywalled site.
- Added a dedicated protected-content sync Edge Function authenticated by `TCT_CONTENT_SYNC_SECRET` held only in GitHub Actions and Supabase.
- While membership remains dark, production can pre-seed the protected article store from articles that are already public today.
- Added narrow public-service exceptions for mandatory evacuation orders, active hurricane/storm-surge warnings, boil-water notices, missing-child alerts, emergency shelter information and emergency bridge closures.
- Paywalled article schema switches `isAccessibleForFree` to false and adds a paywall `hasPart` selector.

## Launch safety

- `TCT_MEMBERSHIP_UI_ENABLED` still defaults to false.
- Existing readers continue to receive complete articles and the existing Advertise UI while the flag is false.
- Browser configuration now fails closed if the membership UI is enabled without a valid Supabase URL/publishable key.
- When membership is enabled, protected-content sync is required; a missing sync secret or failed upload aborts production before commit/deploy.
- The direct `/subscribe.html` page displays a sandbox banner while the membership UI remains dark.

## Supabase additions

New functions:
- `checkout-complete`
- `create-portal`
- `protected-article`
- `sync-protected-articles`

Updated functions:
- `create-checkout` is now pay-first and does not require authentication.
- `stripe-webhook` can create/link a Supabase identity from the Stripe Checkout email and stamps the resulting user id onto the subscription for durable future event routing.

New migration:
- `supabase/migrations/202608090002_membership_payfirst.sql`

## Validation

- Package validation: 35 modules / 119 public exports.
- Workflow-equivalent pytest selection: 817 passed.
- New regressions verify pay-first checkout, passwordless completion, protected-content entitlement, preview/remainder separation, life-safety exceptions, dedicated content-sync secret handling, and launch fail-closed behavior.
