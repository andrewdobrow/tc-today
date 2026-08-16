# TCT v1.13.6.2b — article paywall card-required copy regression

- Fixes the production article paywall template in `tct_engine/membership_paywall.py`.
- Removes the reader-facing words `Card required.` while preserving the actual Stripe Checkout payment-method requirement.
- Keeps the reassurance: `Secure checkout powered by Stripe. You won’t be charged today.`
- Corrects the regression test so `Card required` must be absent from both the root compatibility copy and the production `tct_engine` copy.
- Does not change Stripe configuration, trial behavior, entitlement logic, subscriber chrome, editorial generation, or duplicate handling.
- Existing protected article pages are rehydrated and rebuilt by the normal membership preparation step during `Update Treasure Coast Today`, so the corrected paywall markup is applied to retained protected pages as well as new ones.
