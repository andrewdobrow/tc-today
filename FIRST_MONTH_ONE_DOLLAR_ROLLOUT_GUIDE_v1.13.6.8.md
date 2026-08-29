# v1.13.6.8 rollout guide

1. Apply the root-ready overlay to the current repository.
2. Run **Test Editorial Engine**. Expected: the membership tests and full editorial suite remain clean.
3. Run **Deploy TCT Membership Backend** so `create-checkout` and `checkout-complete` are live with the new Stripe behavior.
4. Open the public Subscribe page and click the **Monthly** plan. Before submitting payment, confirm Stripe Checkout shows **$1.00 due today** and the recurring membership at **$4.99/month** after the first month.
5. Cancel out of Checkout if only validating the order summary.
6. Click the **Annual** plan and confirm it shows **$49/year** and no $1 coupon/free trial.
7. Run one normal **Generate News** with membership enabled. This updates retained article headers/footers and regenerates existing paywall markup from the protected-content snapshot with the new offer.
8. Spot-check the homepage, Subscribe page, one current paywalled article, and one older paywalled article.

Do not change or delete the existing $4.99 monthly Stripe Price or $49 annual Price. Existing subscriptions are intentionally untouched.
