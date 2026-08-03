# Reader Support Recent 50 — Production Review Guide

## Apply

Extract this ZIP at the repository root. It intentionally contains exactly 50 existing article HTML files.

## Validate

1. Run **Test Editorial Engine**.
2. Confirm package validation passes.
3. Confirm 704 tests pass.
4. Run **Update Treasure Coast Today**.

## Production checks

- The 50 newest direct article pages display `images/support-banner.png`.
- Each banner links to the configured Stripe support page.
- Sensitive stories inside the recent 50 display the reader-support banner.
- Older retained articles are not bulk-rewritten.
- Newly generated articles display the support banner automatically.
- `_redirects` and redirect-stub article pages remain unchanged.

## Re-enable paid advertising later

Set the repository variable `TCT_ARTICLE_BANNER_MODE` to `paid_advertising`. The existing sensitive-topic rules and community-resource cards remain in the code and reactivate automatically.
