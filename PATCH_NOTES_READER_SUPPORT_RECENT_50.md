# Reader Support Banner — Recent 50 Article Migration

This consolidated overlay supersedes the earlier sitewide reader-support banner packages.

## What changes

- Replaces the advertising or sensitive-topic house banner on only the 50 newest direct article pages.
- Sends the support banner to the Stripe support page.
- Uses `images/support-banner.png` at 940 × 234 pixels.
- Renders the reader-support banner on every newly generated article, including sensitive topics.
- Keeps the commercial-advertising sensitivity architecture intact behind `TCT_ARTICLE_BANNER_MODE=paid_advertising`.
- Limits retained-page migration to 50 articles so a workflow run cannot rewrite hundreds of historical HTML files.

## Reader-support mode

Default: `TCT_ARTICLE_BANNER_MODE=reader_support`

All new articles receive the support banner. The one-time legacy migration checks only the newest 50 direct pages.

## Future paid-advertising mode

Set the repository variable `TCT_ARTICLE_BANNER_MODE` to `paid_advertising` when commercial banners return. Ordinary stories receive the advertising banner; sensitive stories receive the existing editorial/resource alternatives.
