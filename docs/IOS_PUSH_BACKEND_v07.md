# TCT push-device backend v0.7

This site-repo overlay contains only:

- `supabase/migrations/202610110001_ios_push_device_registry.sql`
- `supabase/functions/push-device/index.ts`
- `scripts/configure_ios_push.ps1` (append-only configuration update; no config file replacement)
- `.github/workflows/deploy-ios-push-device.yml`
- documentation and checks.

It does not send pushes and contains no secrets. Production subscription functions,
news publishing schedules, and Stripe webhooks are untouched. Follow **the complete
sequence in the iOS repo document** `docs/IOS_PUSH_FOUNDATION_v07.md` before
running the new manually triggered workflow.

Privacy: anonymous installations use a random, Keychain-held secret to update or
delete their own registration; the server stores only its SHA-256 digest. APNs
tokens are stored in the restricted registry table. Request authorization from
iOS users before registering. No public SQL/RLS access is granted.

Security note: a public, anonymous registration endpoint is still susceptible
to fake new installations and requires network abuse protection for broad launch.
No APNs sender exists in v0.7, so no article alerts are triggered by this rollout.
