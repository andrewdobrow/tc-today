# TCT v1.13.9.33 — Retained Article Sidebar Static Migration

## Problem
v1.13.9.31 changed the current article renderer and global stylesheet so `.article-side-rail` is static for Mediavine sidebar targeting. However, most existing live article files are retained modern pages with inline template CSS containing:

`position: sticky; top: 118px;`

The retained-page repair intentionally skips modern article shells for performance, so those live pages were never migrated and their inline sticky declaration continued to override the new global CSS.

## Fix
- Normalize only the `.article-side-rail` CSS rule on retained article pages before the modern-shell fast-path skip.
- Replace legacy `position: sticky` with `position: static`.
- Replace legacy `top: 118px` with `top: auto`.
- Do not rebuild article content, paywalls, headlines, related-story selections, or other presentation markup.
- New/current article rendering remains static as introduced in v1.13.9.31.

## Validation
- Added a regression proving a retained modern page is migrated without rebuilding its article shell.
- Targeted sidebar/Mediavine tests pass.
- Exact GitHub editorial pytest selection: 1,348 passed.

## Apply order
Apply this delta on top of v1.13.9.32, then run Test Editorial Engine and Production/Update. The Production generator will migrate the retained live article HTML files as part of its article-shell repair pass.
