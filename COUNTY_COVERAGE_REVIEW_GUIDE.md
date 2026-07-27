# County Coverage Review Guide — v1.11.7.0

Review the first production run using these files:

```text
data/trusted-source-recovery.json
data/category-membership-report.json
data/category-generation-report.json
data/editorial_observability.json
data/story-regression-report.json
archive.json
index.html
```

## Required checks

### Trusted source recovery

Confirm the report records any locally relevant Google News items from trusted publishers. A successful row should contain:

- `result: recovered`
- a non-Google `resolved_url`
- at least 80 source words

A failed recovery must remain `brief` or `thin`; it must not enter article generation. Reported death coverage must not be mislabeled as an obituary merely because it mentions surviving relatives.

### County membership

Confirm:

- `passed: true`
- `missing_county_memberships: 0`
- the P1 Motor Club slug contains both `business` and `st_lucie`
- county/topic cross-posts remain one archive row and one permalink

### Homepage presentation

On the homepage:

1. Select **Business & Development** and confirm the P1 article is eligible to appear.
2. Select **St. Lucie County** and confirm the same permalink is eligible to appear there.
3. Confirm it is not duplicated in Top News.
4. Confirm county panels and “More St. Lucie County Stories” use the same canonical URL.

## Expected console indicators

```text
Trusted source recovery: N/N resolved to usable publisher pages
Category membership contract PASSED (... archive records; ... backfilled)
Homepage permalink uniqueness PASSED
```

The first run will backfill category membership metadata across much of the historical archive. Later runs should report far fewer backfilled records unless new articles or improved locality evidence are added.
