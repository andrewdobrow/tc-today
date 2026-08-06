# ASCII Permalink Integrity Review Guide — v1.13.1.3

## Required workflow

1. Apply this overlay directly over the current repository. It already includes
   v1.13.1.2.
2. Run **Test Editorial Engine**.
3. Run **Update Treasure Coast Today**.
4. Review `data/article-slug-integrity.json` and the workflow log.

## Acceptance criteria

- The complete pytest suite passes.
- `data/article-slug-integrity.json` reports `status: passed` and `ascii_only: true`.
- A clean subsequent migration pass reports `migrated: 0`.
- The Martin County counterfeit Pokémon article is available at the ASCII `pokemon`
  permalink and the old `pok-mon`/Unicode spellings redirect to it.
- Live permalink integrity passes after live publication reconciliation.
- The retained Ethan Boyd article remains:
  `2026-08-06-martin-county-sheriffs-office-seeks-public-help-finding-missing-14-year-old-auti`
- That retained article continues to use:
  `https://treasurecoast.today/images/ethan-boyd.png`
