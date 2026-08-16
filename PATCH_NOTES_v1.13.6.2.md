# TCT v1.13.6.2 — signed-in subscriber chrome

## Reader-facing behavior
- Signed-in entitled subscribers no longer see the Subscribe and Sign in header controls.
- The shared header instead displays `Welcome, <first name>`. If no first name can be resolved, it safely falls back to `Welcome, subscriber`.
- Entitled subscribers no longer see the homepage Treasure Coast Today membership promo card.
- Signed-out readers and signed-in users without an active entitlement continue to see the existing subscription acquisition UI.

## Membership identity
- Adds nullable `profiles.first_name`.
- Stripe Checkout now requires an individual name for new subscriptions.
- Checkout completion and the signed Stripe webhook persist only the first name needed for personalization.
- Existing subscribers with no stored first name get a one-time best-effort recovery from their Stripe Customer/latest Checkout Session. Failure to recover a name never blocks entitlement.

## Sitewide state
- Public retained/generated pages now load the existing membership client when membership UI is enabled.
- The existing local entitlement hint is used only for prepaint suppression of subscription chrome; server-side `membership-status` remains authoritative.
- Protected article text remains server-side entitlement gated.

## Deployment
This release requires applying the new Supabase migration and deploying the membership Edge Functions in addition to the normal Update Treasure Coast Today workflow.
