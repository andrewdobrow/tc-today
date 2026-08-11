# TCT v1.13.5.9c — trial UI regression fix

- Restores the 9a `Limited-time offer` pill on `subscribe.html` after the 9b copy hierarchy update.
- Restores the subscribe header subtext to `Limited time · 7 days free · then $4.99/mo`.
- Corrects an accidental regression assertion typo that expected asset version `1.13.5.9bb` instead of the actual `1.13.5.9b`.
- Preserves the 9b monthly card hierarchy: `Free for 1 week` with `$4.99/month after free trial` beneath it.
- Does not change Stripe, Supabase, pricing, trial duration, or entitlement logic.
