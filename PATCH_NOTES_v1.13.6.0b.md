# TCT v1.13.6.0b — remove card-required paywall copy

- Removes the visible `Card required.` wording from the article paywall.
- Removes the same wording from the membership subscribe landing page.
- Keeps the reassurance: `Secure checkout powered by Stripe. You won’t be charged today.`
- Adds regression coverage requiring `Card required` to remain absent from both reader-facing surfaces.
- Does not change Stripe checkout configuration, the 7-day free trial, pricing, entitlement logic, or payment-method collection behavior.
