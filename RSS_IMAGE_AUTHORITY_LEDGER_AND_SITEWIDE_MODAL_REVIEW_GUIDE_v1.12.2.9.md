# Review Guide — v1.12.2.9

## Expected RSS output

The build should complete with output similar to:

```text
RSS image authority persisted: archive metadata changed=1, article social metadata synced=68, authority items=100
RSS social image contract PASSED: 100 item(s), ...
```

Review both:

- `data/rss-social-image-authority.json`
- `data/rss-social-image-contract.json`

The authority report must contain exactly one row for every RSS item. Each row must identify either a verified source image or the matching green category OG image. The contract report should show `status: passed` and `issue_count: 0`.

No RSS item may use `/images/editorial/` or `/images/fallback/` imagery. Article-visible editorial placeholders may remain in the body while `og:image`, `twitter:image`, structured data, and RSS use the authoritative source-or-category image.

## Expected newsletter behavior

- Desktop loads Kit modal `be625cadfe`.
- Mobile loads the same modal.
- Sticky embed `4edef44197` is not loaded.
- The masthead receives no newsletter offset.
- Mobile leaves a visible dismissible border around the modal.
- Existing inline newsletter forms remain unchanged.
