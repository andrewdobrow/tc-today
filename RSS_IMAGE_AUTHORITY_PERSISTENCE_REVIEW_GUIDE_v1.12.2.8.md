# Review Guide — v1.12.2.8 RSS Image Authority Persistence

## Expected production behavior

The build should print a persistence message when live source imagery is recovered, followed by a passing RSS image contract. Example:

```text
RSS image authority persisted: archive metadata changed=1, article social metadata synced=4
RSS social image contract PASSED: 100 item(s), 42 source image(s), 58 category OG fallback(s), 100 article metadata match(es)
```

`data/rss-social-image-contract.json` should report:

- `status: passed`;
- `issue_count: 0`;
- exactly one RSS image per item;
- no `images/editorial/*` or `images/fallback/*` image in RSS;
- `persisted_source_images` equal to the number of source-image RSS items represented durably in the archive;
- article Open Graph metadata matching every RSS image where an article file exists.

## Image policy

1. Exact verified source image when available.
2. Matching green category OG image otherwise.
3. Reusable editorial photographs remain page-display assets only.

## Regression scenario

An archive row with an editorial placeholder and a live object with a verified publisher image must:

- emit the publisher image in RSS;
- persist it as `source_image_url`;
- synchronize article social metadata;
- preserve the visible editorial image;
- pass the runtime contract.
