# Review Guide — v1.13.6.7d

## Apply
Upload the overlay at repository root after v1.13.6.7c.

## Test
Run **Test Editorial Engine** first.

Expected: green workflow.

## Production + bakeoff
If test passes, run **Update Treasure Coast Today** with:

- Straight Sonnet 4.5 vs Sonnet 5 model bakeoff: **OFF**
- Sonnet 5 assignment editor + Sonnet 4.5 writer shadow: **ON**

Production remains Sonnet 4.5. The shadow remains publication-isolated and final-pipeline aligned.

## What to verify in the production log
On the first production run after 6.7d, expect a line similar to:

`Source-retirement cleanup retired 2 stale archive record(s) (1 canonical redirect(s))`

Also continue to expect the v1.13.6.7b ingestion messages:

`Source policy excluded X Hometown News item(s)`

## Required Hometown checks
After the run:

1. The Aug. 22 `$600K` gold-scam URL must redirect to the Aug. 13 canonical.
2. The Aug. 22 attainable-housing-trust URL must no longer appear in archive recovery, category cards, Top Stories, Latest News, sitemap/news-sitemap, or homepage hero selection.
3. The housing URL itself should contain a noindex handoff to Indian River coverage.
4. No unrelated historical Hometown article should be retired by this policy.
5. `data/source-retirement-cleanup-report.json` should show:
   - `policy_count: 2`
   - first cleanup run: `retired_count: 2`, `redirect_count: 1`, `mismatch_count: 0`
   - later idempotent runs may show `retired_count: 0` because the rows are already gone.

## Bakeoff files to upload
Upload the fresh production repo plus:

- Generate News log
- `data/assignment-editor-shadow-review.md`
- `data/assignment-editor-shadow-answer-key.json`
- `data/assignment-editor-shadow-report.json`
- `data/model-usage-report.json`

Score the blind review before opening the answer key.

## Watch item
Do not bundle another identity change into this increment. Continue observing the Cornelius Ivory material-update behavior. If a fresh same-story development is again generated correctly but lost during final publication, make that the next isolated pipeline fix.
