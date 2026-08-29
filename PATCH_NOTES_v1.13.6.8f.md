# TCT v1.13.6.8f — Compact Membership Chrome Restoration

## Purpose
Restore the v1.13.6.8c compact membership CTA source that was absent from the CI checkout used for the 8d/8e validation run.

## Behavior
- Header remains: `Subscribe` / `Limited time · $1 first month`.
- Compact footer CTA remains: `Get first month for $1` / `Limited time · $1 first month`.
- Removes `then $4.99/mo` from compact site chrome.
- Does **not** remove the required renewal disclosure from the actual paywall, Subscribe pricing, or Stripe checkout.
- Does not alter membership billing, entitlement, terminal semantic authority, or article paywall design.

## Validation
- Package validation: 38 modules / 122 public exports.
- CI-equivalent suite: 1,026 passed / 0 failed / 41 existing datetime deprecation warnings.
