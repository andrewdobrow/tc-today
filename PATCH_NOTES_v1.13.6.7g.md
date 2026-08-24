# v1.13.6.7g — Corrected Historical Record Retirement + 6.7f Cumulative-Safe Packaging

## Problem
A Treasure Coast Today article published Aug. 22, 2026 from Hometown News coverage described a July 17 arrest and incorrectly repeated an outdated residential address for Collin Ryan Smith. The source publication had later corrected the address, but TCT's stale republication still said the 4900 block of Corsica Square.

The article should not remain eligible for live recovery because it was a false-fresh Hometown republication, but simply deleting it would erase the correction record.

During preparation of this hotfix, the v1.13.6.7f overlay was also found to contain a full `scripts/generate.py` from the pre-v1.13.6.7d base. Applying that file after 6.7d would overwrite the Hometown legacy cleanup implementation. This package therefore carries forward both feature families safely.

## Changes
- Adds the Smith Aug. 22 slug to `data/source-retirement-cleanup.json` with action `retire_corrected_record`.
- Corrects `4900 block of Corsica Square` to `5000 block of 33rd Avenue` in the retained article page.
- Removes any remaining `Corsica Square` references from the retained page.
- Adds a visible correction notice dated Aug. 24, 2026 without repeating the incorrect neighborhood name.
- Adds `noindex,follow` to the corrected historical page.
- Removes the slug from archive/live recovery and all active hero/card selection surfaces while preserving its direct URL as a historical correction record.
- Adds fail-closed correction validation: configured wrong text must be found, forbidden wrong text may not remain, and the original article page must exist.
- Preserves the v1.13.6.7d Hometown legacy cleanup and the v1.13.6.7f Sonnet 5 topic-category-fit adjudication in the same `scripts/generate.py`.
- Includes the v1.13.6.7f assignment-editor module/test changes so this overlay supersedes the earlier 6.7f ZIP.

## Expected first production log
`Source-retirement cleanup retired 1 stale archive record(s) (0 canonical redirect(s), 1 corrected historical record(s))`

If the record has already been removed by a manual intervention, the count may be zero.

## Validation
- Hometown retirement + assignment editor: 28 passed.
- Broader relevant release suite: 39 passed.
- Package validation: 38 modules / 119 public exports.
- Python compilation: passed.
