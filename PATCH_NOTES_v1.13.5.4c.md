# TCT v1.13.5.4c — Launch-aware banner test hotfix

## Why
The Test Editorial Engine suite still contained one regression that inspected the newest 50 mutable production article files and required the legacy Support TCT banner. That contract is invalid once membership launch state intentionally removes that banner.

## Changes
- Replaces the mutable-production-state banner assertion with a synthetic launch-state regression.
- Confirms the reader-support migration is a no-op when membership UI is enabled, so the retired Support TCT banner cannot be reconstructed after launch.
- Passes `TCT_MEMBERSHIP_UI_ENABLED` from the repository variable into the Test Editorial Engine job so CI evaluates the same launch state as production.
- Strengthens the workflow regression to require membership launch state in both workflows.

## Scope
Test/workflow only. No article content, paywall, Stripe, Supabase, freshness, duplicate, newsletter, or editorial behavior is changed.
