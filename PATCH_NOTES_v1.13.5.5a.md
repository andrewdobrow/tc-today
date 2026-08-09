# TCT v1.13.5.5a — Protected Sync Self-Heal

This hotfix addresses the launch migration failure:

`Protected article sync failed (400): {"error":"Batch must contain 1-100 articles."}`

That response is emitted by the pre-snapshot version of the `sync-protected-articles` Edge Function. The repository client was sending the new `action: snapshot` request while the live function was still serving the older batch-only contract.

## Changes

- Production now probes the protected-content snapshot capability before attempting the migration.
- If the live function is the older batch-only version, production automatically deploys the current `sync-protected-articles` function using the already-configured Supabase GitHub credentials, then continues.
- The manual membership-backend deploy now explicitly deploys `sync-protected-articles` and verifies the snapshot capability before it can report success.
- The Python sync client emits a specific stale-backend diagnostic for this exact contract mismatch.
- Regression tests require the self-healing deployment path and backend verification.

No paywall design, teaser length, fade, Kit form, Stripe, entitlement, stale-story, duplicate, or editorial logic is changed by this hotfix.
