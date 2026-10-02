# TCT v1.13.9.73 — obvious mobile newsletter dismissal link

Apply on top of `.72`.

## Why
The `.72` safe-area adjustment made the Kit close control reachable in Reddit's iOS in-app browser, but the usable tap target remained too precise. A reader should never have to hunt for a tiny X to continue reading.

## Changes
- Adds a first-party mobile-only dismissal control directly after Kit's Subscribe button:
  - `No, I'd rather not be in the know`
- Gives the control a full-width 44px minimum touch target.
- Uses a MutationObserver so the control is added after Kit injects its modal into the document.
- Delegates dismissal to Kit's existing `.formkit-close` control, preserving Kit's own modal close/suppression lifecycle.
- Includes an Escape-key fallback if Kit changes its close-button markup in the future.
- Desktop remains unchanged.
- Does not change modal timing, newsletter form submission, membership/paywall behavior, Mediavine, or editorial generation.

## Validation
- `tests/test_newsletter_mobile_modal.py`
- `tests/test_newsletter_inline_form.py`
- `tests/test_article_newsletter_delivery_contract.py`
- Result: 15 passed
- `node --check main.js` passed
