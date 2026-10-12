# October 12, 2026 — expired flood-warning repeated-publication fix

Apply to the **website** repository (`tc-today`), not `tct-ios`.

This overlay is based on the website archive supplied for the October 12 handoff.
Before applying, compare the included `scripts/generate.py` and
`data/source-retirement-editor-overrides.json` with the current `main` branch;
merge rather than blindly overwrite if either file has changed since upload.

## Changes

- `data/source-retirement-editor-overrides.json`: retains all four prior editorial
  entries and adds the exact October 12 article retirement (fifth entry).
  The October 11 warning retirement additionally opts into a **14-day**
  identical-headline date-shifted republication guard.
- `scripts/generate.py`: resolves that editor-approved opt-in at live-feed,
  archive-recovery, and final article-retirement stages. All other editorial
  retirements remain exact-slug only. Does not ban legitimate storm/aftermath
  reporting or other NWS warnings. The direct NWS weather-alert generator
  remains disabled.
- `articles/2026-10-12-flash-flood-warning-hits-stuart-hobe-sound-palm-city-and-coastal-martin-county.html`:
  immediate noindex retired-story handoff page, until normal generation
  reconciles all archive/feed/sitemap surfaces.
- `tests/test_expired_flash_flood_warning_retirement.py`: adds reproduction
  coverage for date-shifted retirement and unrelated-story preservation.

## Deploy & verify

1. Commit the files to website `main`, preserving other recent changes.
2. Run **Test Editorial Engine** and require green; local targeted tests pass,
   but the whole production suite has not been run on GitHub.
3. Trigger **Update Treasure Coast Today** to rebuild all discovery surfaces
   and commit/generated publish output. Require green. Avoid relying on a
   future scheduled run to remove a currently misleading warning.
4. Verify the Oct. 12 article no longer serves the warning, is `noindex` and
   leads to the archive. Verify the Oct. 11 article is still retired.
5. Verify neither date appears in home/Martin/categories/archive/RSS/sitemaps.
   Inspect the next run for reappearance. Do NOT redirect to unrelated articles.

Scope: This blocks the **known identical-headline** republication for the
editor-specified 14 days. It is not a universal timestamp verification system
for all incoming NWS-related feed stories. That broader validation requires
reliable source alert identifiers and official issue/expiry metadata at
publication time; do not infer active alert status from headline alone.
