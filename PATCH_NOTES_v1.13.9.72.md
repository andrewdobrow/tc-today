# TCT v1.13.9.72 — Reddit/iOS newsletter modal safe-area fix

Apply on top of v1.13.9.71.

## Problem
In Reddit's iOS in-app browser, browser chrome can overlap Kit's newsletter-modal close control, effectively trapping users behind the email modal.

## Changes
- Adds extra mobile viewport breathing room around Kit modal forms.
- Increases bottom clearance for iOS/in-app browser chrome and safe-area insets.
- Keeps the Kit modal narrower on small screens so the close control is farther from the physical/browser edge.
- Gives the modal close control a 44x44px minimum touch target and elevates its stacking level.
- Does not change the newsletter trigger, Kit form, desktop behavior, paywall, or Mediavine integration.

## Validation
- `tests/test_newsletter_mobile_modal.py`: 5/5 passed.
- Newsletter-related focused suite: passed.
- Python compile check for modified test passed.

## Files
- `style.css`
- `tests/test_newsletter_mobile_modal.py`
