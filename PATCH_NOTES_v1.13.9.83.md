# TCT v1.13.9.83 - targeted published-copy repair support

## Purpose
Repair the already-published Oct. 2 tow-yard article sentence that reads:

`video and phone and vehicle search warrants`

without regenerating the article, changing any facts, changing the publication timestamp, or creating a visible update label.

## Current article repair
Canonical slug:

`2026-10-02-two-miami-women-charged-after-tow-yard-shooting-near-stuart-sparks-school-lockou`

The exact slug-scoped copy edit changes only:

`video and phone and vehicle search warrants`

into:

`video and search warrants involving phones and vehicles`

This wording matches the source-grounded construction already used by the v1.13.9.81 newsroom copy-desk regression fixture.

## Reusable copy-edit mechanism
`article-content-overrides.json` now supports literal `body_replacements` for surgical corrections to already-published generated copy.

Copy-edit-only overrides may set `mark_meaningful_update: false`. In that mode the generator:

- repairs the canonical archive body;
- repairs matching `data.json` body text;
- repairs matching in-memory live article bodies;
- repairs the rendered article HTML, including HTML-escaped text;
- does not add an `UPDATE` block;
- does not rebuild the paywall/article shell;
- does not change publication or modified timestamps;
- does not mark the article as a substantive/meaningful update.

All existing content overrides keep their prior meaningful-update behavior by default.

## Validation
Focused regression set:

`16 passed`

Production-equivalent suite, split into four chunks to stay inside the local execution ceiling:

- 371 passed
- 375 passed
- 323 passed
- 416 passed
- **1,485 passed total, 0 failed**

Package validation:

`42 modules imported and 123 public exports verified.`
