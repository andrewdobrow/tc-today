# Treasure Coast Today v1.13.4.1 — Membership CLI Import Fix

This is a narrow follow-up to v1.13.4.0.

## Fixed

GitHub Actions executes membership helper scripts by file path (`python scripts/...`). In that execution mode Python places the `scripts/` directory, not necessarily the repository root, at the front of `sys.path`. The new v1.13.4.0 helpers imported `tct_engine` before explicitly adding the repository root, so production could fail with:

`ModuleNotFoundError: No module named 'tct_engine'`

Both membership CLI helpers now bootstrap the repository root before importing `tct_engine`:

- `scripts/prepare_membership_paywall.py`
- `scripts/sync_protected_articles.py`

A regression test now launches both files exactly as GitHub Actions does, so this class of import-path failure cannot silently return.

No membership UI is enabled by this patch and no Supabase/Stripe configuration changes are required.
