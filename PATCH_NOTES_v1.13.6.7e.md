# TCT v1.13.6.7e — Universal Article Paywall Policy

## Purpose
Remove the unapproved public-service/life-safety paywall exemption introduced in v1.13.4.0.

TCT membership policy is now simple: normal article pages that are eligible for the protected-content split go through the same membership paywall pipeline regardless of subject matter. Emergency/public-service wording no longer bypasses membership protection.

## Changes

- Removed `is_public_service_exception()` from the membership paywall helpers.
- Removed the public-service bypass from `scripts/prepare_membership_paywall.py`.
- Removed the public-service bypass from `scripts/sync_protected_articles.py`.
- Removed the `public-service free` counter from paywall-preparation output.
- Kept redirects, already-protected pages, protected-content fail-closed behavior, and the existing minimum-content split safeguards unchanged.
- No changes to Stripe checkout, Supabase entitlement, protected-content transport, editorial identity, publication identity, or model/bakeoff logic.

## Permanent regressions

1. An active Amber Alert / missing-child story is included in protected-content scanning.
2. A boil-water/public-service story receives the membership paywall when it is long enough for the standard protected-content split.
3. A normal crime story that merely says Flock cameras can help with `locating missing children` is still protected; incidental public-service language has no exemption effect.
4. Protected export retains the complete article body and the public page receives the standard paywall/schema treatment.

## Validation

- Focused membership/paywall + provenance suite: 59 passed.
- Exact protected-content regression subset: 25 passed.
- Package validation: 38 modules imported / 119 public exports verified.
- `py_compile`: PASS for all changed Python files.
- Broad `tests/` run from the supplied repo snapshot: 944 passed, 45 warnings, with 7 pre-existing collection/setup errors caused by the snapshot lacking root `engine.py`; none involve membership/paywall code.

## Expected production effect

On the next membership-enabled production preparation, previously full-public articles that qualify for the normal protected-content split—including articles that had been skipped solely because of the former public-service exemption—are eligible to be converted to the standard preview + paywall form and synced to protected storage.
