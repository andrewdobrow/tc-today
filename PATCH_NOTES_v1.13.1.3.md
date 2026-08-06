# v1.13.1.3 — ASCII Permalink Integrity

## Purpose

Prevent valid articles with accented characters in their headlines from being
published under a filename that the final permalink-integrity gate cannot resolve.

The failed production run created the counterfeit Pokémon article with a Unicode
slug while the live-binding layer normalized the same URL to `pok-mon`. The article
existed, but the live Martin County hero could not prove that its page existed and
the deployment correctly failed closed.

## Included cumulative work

This overlay includes all files from v1.13.1.2 Missing-Person Identity Continuity.
The retained Ethan Boyd article remains the canonical page and keeps the editorial
image override at `/images/ethan-boyd.png`.

## Permanent correction

- Generated and custom permalinks now use one shared ASCII-only NFKD normalization.
- `Pokémon` becomes `pokemon`; `fiancée` becomes `fiancee`.
- Existing unsafe archive slugs are migrated before identity and category loading.
- Substantive article HTML is copied to the safe canonical filename.
- Historical Unicode, ZIP-escaped and old hyphen-normalized spellings become
  noindex redirects.
- Archive and redirect metadata are updated atomically.
- Migration is idempotent and fails closed on a canonical-path collision or a
  missing substantive article file.

## Production repairs

- The Martin County counterfeit Pokémon article is migrated to:
  `2026-08-06-martin-county-investigators-warn-of-counterfeit-pokemon-card-scams-after-collect`
- The older Hobe Sound fiancée article is migrated to an ASCII-safe permalink.
