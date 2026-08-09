# Treasure Coast Today v1.13.5.2 — Python 3.11 Launch Compatibility Hotfix

This incremental hotfix applies on top of v1.13.5.1.

## Fix
- Rewrites the conditional `/subscribe.html` sitemap fragment so it does not use a same-quote nested f-string.
- The previous expression is valid under newer Python f-string parsing rules, but GitHub Actions runs Python 3.11, where it fails before tests with `SyntaxError: f-string: unmatched '('`.
- Membership launch behavior is unchanged: `/subscribe.html` is included in the sitemap only when `TCT_MEMBERSHIP_UI_ENABLED=true`.
- Adds regression coverage for both dark-launch and launch sitemap behavior plus the Python-3.11-incompatible source pattern.

No Supabase, Stripe, membership entitlement, paywall, or editorial identity behavior changes in this patch.
