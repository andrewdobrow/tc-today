# TCT v1.13.9.84 — protected copy-edit persistence fix

## Problem

The v1.13.9.83 slug-scoped copy edit was correctly applied by `scripts/generate.py`, but an already-paywalled article could later be rehydrated by `scripts/prepare_membership_paywall.py` from the protected-content Supabase snapshot. Because that snapshot predated the copy edit, it could restore the stale full article body and then re-export that stale body back to the protected store.

This made the old wording reappear after the generator had already corrected it.

## Fix

`scripts/prepare_membership_paywall.py` now:

- loads durable `body_replacements` from `data/article-content-overrides.json`;
- reapplies those exact, slug-scoped replacements after protected-store rehydration and before article re-splitting;
- handles both raw and HTML-escaped text;
- writes the corrected full body into the protected export, so the subsequent protected-store sync cannot resurrect stale wording;
- logs the actual number of protected copy-edit replacements applied.

The copy edit remains non-substantive. It does not mark a meaningful update, change publication time, add an UPDATE banner, or alter canonical identity.

## Current tow-yard regression

The protected-store snapshot form of:

`video and phone and vehicle search warrants`

is now converted before re-splitting to:

`video and search warrants involving phones and vehicles`

for the exact Oct. 2 tow-yard article slug already recorded in the v1.13.9.83 content-override ledger.

## Files changed

- `scripts/prepare_membership_paywall.py`
- `tests/test_membership_protected_copyedit_persistence.py`

## Validation

- Focused membership/copy-edit regression suite: **61 passed**.
- Four-way production-equivalent suite: **1,487 passed, 0 failed** total.
- `python scripts/validate_package.py`: **42 modules imported, 123 public exports verified**.
