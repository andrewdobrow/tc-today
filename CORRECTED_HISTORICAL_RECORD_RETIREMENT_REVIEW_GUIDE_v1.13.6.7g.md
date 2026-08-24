# Review Guide — v1.13.6.7g

## Apply order
Apply this overlay directly on the current repository. **Do not apply the older v1.13.6.7f overlay afterward.** This package already includes the 6.7f assignment-editor changes and preserves the 6.7d Hometown cleanup code.

## Smith article checks
Target slug:
`2026-08-22-vero-beach-man-arrested-on-attempted-murder-charge-after-birthday-party-assault`

After production:
1. The direct URL should still load as an article page, not redirect elsewhere.
2. The article should say `5000 block of 33rd Avenue`.
3. The rendered article should contain no `Corsica Square` reference and no `4900 block` address reference.
4. The article should show a correction notice dated Aug. 24, 2026 stating that the residential address was corrected.
5. The page should contain `noindex,follow`.
6. The slug must not appear as a hero/card in Crime & Safety, Indian River County, Top Stories, or archive recovery.
7. `data/source-retirement-cleanup-report.json` should report the corrected historical record when it is first retired.

## Assignment-editor checks retained from 6.7f
- Topic pages require Sonnet 5 category-fit adjudication before assignment.
- County pages do not require topic-fit adjudication.
- A rejected topic source cannot later be selected as hero/card.

## Expected first-run line
`Source-retirement cleanup retired 1 stale archive record(s) (0 canonical redirect(s), 1 corrected historical record(s))`
