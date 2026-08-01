# Newsletter Inline Form Review Guide — v1.12.1.1

## Expected behavior

1. Open the homepage and switch among category tabs.
2. Confirm one inline Kit form appears directly beneath the currently displayed hero and does not repeat when categories change.
3. Open a standard article and a custom article.
4. Confirm one inline form appears after the article body and before sharing/related-story controls.
5. Confirm the existing sticky bar still appears according to its Kit display rules.
6. Inspect desktop and mobile widths. The inline form should remain inside the hero or article content column without horizontal overflow.
7. Submit a test email from each placement and verify both submissions reach the intended Kit form associated with UID `30e15672d3`.
8. Confirm each page requests the inline script only once:
   `https://treasure-coast-today.kit.com/30e15672d3/index.js`

## Rollback

Remove `_newsletter_inline_embed("article")` and `_newsletter_inline_embed("category-hero")` from `scripts/generate.py`, then remove the corresponding `.newsletter-inline-slot` rules from `style.css`.
