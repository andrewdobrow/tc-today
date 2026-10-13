# Step 1C — Account deletion backend (`tc-today`)

**SAFETY:** This ZIP does not deploy anything. Do not use your own live subscriber account to test deletion. Step 1A website publishing can run independently, but avoid deploying these backend changes while conflicting backend workflows run.

## Exact order
1. Download this ZIP and upload **only** `APPLY_TCT_ACCOUNT_DELETION_BACKEND.py` to the root of `andrewdobrow/tc-today` on GitHub; commit the uploaded script.
2. Open the website Codespace. Run `git status`; if clean, run `git pull --ff-only origin main`.
3. Run `python APPLY_TCT_ACCOUNT_DELETION_BACKEND.py`.
4. Inspect `git diff -- supabase/functions/_shared/membership.ts supabase/functions/stripe-webhook/index.ts supabase/functions/checkout-complete/index.ts supabase/config.toml`; inspect the **new untracked** Edge Function and SQL migration with `git status` and open them.
5. Commit *all* modified files AND the new function/migration using:
   `git add supabase/functions/_shared/membership.ts supabase/functions/stripe-webhook/index.ts supabase/functions/checkout-complete/index.ts supabase/functions/delete-account/index.ts supabase/migrations/202610120002_membership_account_deletion_guards.sql supabase/config.toml`
   `git commit -m "Implement guarded account deletion and Stripe replay suppression"`
   `git pull --rebase origin main`
   `git push origin main`
6. **Before deploying Edge Functions**, in **Supabase → SQL Editor** run the **entire new SQL migration** from `supabase/migrations/202610120002_membership_account_deletion_guards.sql`. This creates the anti-replay table. Running it again is safe.
7. In **GitHub → tc-today → Actions**, manually run **Deploy TCT Membership Backend** on `main` (the website editorial publisher is a separate workflow). Verify the whole deployment ends green, including the new `delete-account` function.
8. In Supabase Edge Functions, confirm `delete-account`, `stripe-webhook`, and `checkout-complete` show new deployments. Verify existing membership sign-in, checkout, and webhook health with a NONDESTRUCTIVE test before enabling the iOS button.
9. Then apply the separate iOS overlay, run the unsigned iOS build, create the signed Ad Hoc build, and test deletion with a **dedicated disposable non-admin test account**. Check Stripe canceled immediately; Supabase Auth user/profile/subscriptions deleted; old Stripe webhook does not re-create the user; ordinary portal cancellation does not delete any account.

## What it changes
- New authenticated `delete-account` Supabase Edge Function: explicit confirmation, verify billing identities, prevent shared-customer cancellation, persist anti-replay digests, cancel all identifiable TCT renewals immediately, verify no TCT renewals remain, then delete Supabase Auth user (which cascades profiles/subscriptions).
- New SQL migration for hashed replay suppression IDs without plaintext emails/customer IDs. Service role only.
- Shared membership guard and updated `stripe-webhook` and `checkout-complete` prevent late Apple/Stripe events from recreating deleted identities. Existing normal Stripe subscriptions are otherwise unaffected.
- `supabase/config.toml` JWT requirement for the new function.

## Exceptions and follow-up
- If Stripe cancellation, billing linkage checks, or Auth removal fail, the endpoint returns an error instead of falsely reporting success. Some partial failures may require support intervention. Do not assume a failed response means the billing situation is unchanged.
- Stripe billing records/invoices are not automatically purged or refunded. User-facing copy must be consistent with privacy policy and legal retention obligations.
- We still need to confirm the **Stripe Customer Portal** cancellation setting is at-period-end for the *separate* Manage or Cancel Subscription action (Step 1D).
- SQL preflight inventoried account identifier columns in `profiles` and `subscriptions`, but does not prove that no other future data processors store related personal information.
