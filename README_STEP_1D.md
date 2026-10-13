# Step 1D — TCT Subscription Terms + website disclosure patch

## Scope

- **Website repository:** `tc-today` only.
- Adds **`subscription-terms.html`** modeled on the repository's **current** `privacy.html` page, so it follows your deployed privacy-page layout and legal operator wording. Does not alter `privacy.html`.
- Updates `subscribe.html` to link the terms and privacy policy **near both plan buttons**, expand the cancellation FAQ, distinguish account deletion, and include a footer link.
- Monthly $1 first month then $4.99/month; annual $49/year; auto-renewal; ordinary cancellation at period end; no routine prorated refunds except applicable law or TCT-approved exceptions; account deletion immediately ends access and cancels renewals.
- Does **not** change Stripe Checkout, Portal configuration, Supabase, iOS, or the editorial workflow.
- The script validates target anchors and refuses to overwrite an existing customized Subscription Terms page. It can be safely rerun after successful application.

## REQUIRED PRE-PUBLISH CHECK (do not skip)

In **Stripe Dashboard → Live mode → Settings → Billing → Customer portal** (label/navigation may vary), check that **subscription cancellations are allowed** and the cancellation timing is set to **at the end of the billing period** rather than **immediately**. Also ensure any refund/proration settings are consistent with the policy. The website code launches the Stripe Customer Portal but **does not set these policies** itself. Stripe calls the desired setting `features.subscription_cancel.mode = at_period_end`.

Do not mistake the **Delete Account** action for an ordinary cancellation: deletion is designed to cancel immediately and remove access. That is the agreed separate exception.

## Apply, inspect, publish (after Stripe portal setting verified)

1. Upload `APPLY_TCT_SUBSCRIPTION_TERMS.py` at the root of the **tc-today** GitHub repository, and commit the script. Do not confuse with the iOS repository.
2. Open your `tc-today` Codespace. Run `git status`, and stop on unexpected uncommitted changes. Then run `git pull --ff-only origin main`.
3. From the repository root run `python APPLY_TCT_SUBSCRIPTION_TERMS.py`.
4. Review `git diff -- subscribe.html` and open/read the NEW `subscription-terms.html`. Run `git diff --check` and `git status --short`. A new untracked HTML page is not included in an ordinary `git diff` until staged.
5. Stage the exact files: `git add subscribe.html subscription-terms.html`; then `git diff --cached --check` and `git diff --cached --stat`. Confirm the two page files (no unintended files).
6. Commit: `git commit -m "Add subscription terms and clearer renewal disclosures"`.
7. Sync and push: `git pull --rebase origin main`; `git push origin main`; verify `git status`.
8. In **tc-today → GitHub Actions**, manually run **Update Treasure Coast Today — Bounded Runtime** on `main`. This is the website publishing workflow; a push alone does not publish website changes. Avoid starting a duplicate concurrent run.
9. Wait for the entire run to complete GREEN. Verify the GitHub Pages deploy job and latest commit if the workflow reports publishing steps.
10. Verify the live pages with hard-refresh: `https://treasurecoast.today/subscription-terms.html` and `https://treasurecoast.today/subscribe.html`. On mobile, check the terms link beneath the plan buttons, both prices, FAQ, and footer link. Check that existing Stripe checkout can still be opened, but do not charge a card unless doing an approved controlled test.
11. **Next separate iOS phase:** add `Subscription Terms` link inside the Account screen, build unsigned, build signed Ad Hoc, and verify on iPhone. The website patch alone does not change the app.

## Operator/LLC timing

The page currently identifies the operator as Andrew Dobrow until Florida approves TCT LLC. Update all operator notices consistently when registration is approved. This draft is not a substitute for tailored legal advice.
