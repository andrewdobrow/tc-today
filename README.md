# Step 1C — Fix account deletion marker order

The first deletion test failed because a legacy Stripe **test-mode** customer was queried using the site's **live-mode** Stripe key. This is a legitimate refusal to delete; however, the initial backend implementation wrote permanent replay-guard markers *before* Stripe verification, leaving an existing account incorrectly marked as deleted. This fix moves marker creation **after** all Stripe renewals have been cancelled and verified, but **before** the Supabase Auth user is deleted. Any new attempt that fails Stripe verification will not create new markers.

**Scope:** `supabase/functions/delete-account/index.ts` only. No changes to the website publisher, Stripe settings, database schema, or iOS binary. Existing historical markers are not automatically removed by this patch.

1. Upload `APPLY_TCT_DELETION_MARKER_ORDER_FIX.py` to repository root of **`tc-today`**, commit on `main`.
2. In `tc-today` Codespace, `git status` and ensure clean; `git pull --ff-only origin main`.
3. Run `python APPLY_TCT_DELETION_MARKER_ORDER_FIX.py`.
4. Run `git diff --check`, `git diff -- supabase/functions/delete-account/index.ts`. Ensure **only** this Edge Function changed and that the replay marker is now after the catch block logging `delete-account Stripe cancellation incomplete` and before `admin.auth.admin.deleteUser`.
5. `git add supabase/functions/delete-account/index.ts && git commit -m 'Avoid deletion markers when Stripe verification fails' && git pull --rebase origin main && git push origin main`.
6. In GitHub Actions run **`tc-today` → `Deploy TCT Membership Backend`** manually on `main`. Verify overall green and the new `delete-account` function deployment in Supabase.
7. Do not retry deletion of the original test-mode customer account. It already has replay markers created by the previous version. It needs a separate, **targeted cleanup** after inspecting exactly which hashes are present; do not clear all tombstones.
8. No additional iOS build is necessary; future iOS delete-account requests use the deployed endpoint.

This does **not** prove cancellation of paid subscriptions, which still needs a controlled test of the real Stripe billing flow.
