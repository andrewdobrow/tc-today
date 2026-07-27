# TCT v1.11.5.2 — Emergency Nonstory Hero and Mobile Comparison Guard

## Production incident

A model-generated status sentence was published as a real Local Government article and selected as the homepage hero:

`No local government stories available for Treasure Coast coverage`

The prior detector recognized several `No ... stories available` forms but did not allow a trailing `for Treasure Coast coverage` phrase. Because the same predicate powers generation cleanup, archive purging and the final deployment contract, the sentence escaped every layer.

## Fixes

- Expands the deterministic nonstory predicate to reject status headlines with trailing geography or coverage phrases.
- Blocks nonstories from the normal and structural front-page candidate pools.
- Makes the front-page fallback fail closed when no real story exists.
- Adds a final selected-hero assertion before rendering.
- Causes the existing nonstory archive purge to remove the bad article record and replace its page with a `noindex,follow` redirect to the archive on the next run.
- Makes product comparison tables horizontally scrollable on narrow screens instead of compressing columns.
- Prevents comparison-cell words from splitting into fragments with explicit `overflow-wrap`, `word-break` and hyphenation rules.
- Advances the product-guide template to `1.6-scroll-safe-comparison-table` so existing guides regenerate.

## Safety

- Custom/editor-authored articles remain exempt from phrase-based nonstory detection unless explicitly marked as structural placeholders.
- No publication gate is weakened.
- The workflow will fail rather than publish a placeholder as the homepage hero.
