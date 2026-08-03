# Reader Support Recent-50 Preflight Review Guide v3

## Apply

Extract this overlay at the repository root after the recent-50 reader-support overlay.

## Expected Test Editorial Engine behavior

Before validation, the workflow prints a line similar to:

```text
Reader-support preflight: 50 checked, 3 migrated
```

The migrated count may be zero after the first successful production commit.

The workflow should then report:

- package validation passed;
- 706 tests passed;
- no failure from `test_most_recent_50_published_articles_use_support_banner`.

## Expected production behavior

The production workflow normalizes no more than the current 50 direct article pages before pytest, generates new pages using the support banner contract, and commits only pages that actually required repair.

## Paid advertising switch

When `TCT_ARTICLE_BANNER_MODE` is changed to `paid_advertising`, the preflight becomes a no-op. The existing sensitive-topic commercial-ad restrictions and resource notices remain available.
