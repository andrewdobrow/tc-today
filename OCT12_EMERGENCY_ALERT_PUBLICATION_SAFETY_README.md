# TCT Emergency Alert Publication Safety — October 12, 2026

## Why this differs from the prior two fixes

The actual National Weather Service Melbourne warning for **northeastern Martin County** was issued **October 11, 2026 at 5:23 p.m. EDT** and expired **October 11 at 7:00 p.m. EDT**, product `/O.NEW.KMLB.FF.W.0008.261011T2123Z-261011T2300Z/`. A generic editorial feed kept recirculating that bulletin under new TCT publication dates and **different AI-written headlines**. Previous fixes only suppressed known URLs or an identical dated slug stem, so the October 12 "...Until 7 PM" article was not covered.

This package is a fail-closed safety patch to the *regular editorial publication pipeline*; the dedicated NWS automatic article publisher was already disabled.

## Changes

- `data/source-retirement-editor-overrides.json`: preserves previous editorial decisions and all prior October 11/12 blocks, adds the **third reported permalink** to permanent retirement.
- `articles/2026-10-12-flash-flood-warning-hits-coastal-martin-county-until-7-pm.html`: immediately replaces the inaccurate article with a noindex retirement/Archive handoff, even before the next editorial run.
- `scripts/generate.py`: prevents newly generated *present-tense emergency-warning announcements* from being written into article pages when the ordinary editorial feed has no verified NWS alert ID, expiry, cancellation state, and coverage confirmation. Applies independently of article slug or its newly minted date. Applies to auto-generated flash flood, tornado, and severe-thunderstorm warning/watch/advisory announcements (including an "NWS Issues..." or "County Under..." headline). Keeps manually edited/custom articles and retrospective reporting eligible. Blocks late re-introduction through homepage, category, front-page hero, archive recovery, and RSS/sitemap archive input. Adds a hard final invariant: if an active-alert claim survives any check, the workflow must fail **instead of deploying it**.
- `tests/test_emergency_alert_publication_safety.py`: new regression tests covering the third article, multiple headline changes, safe post-storm articles, custom/manual news, archive/live recovery, and final fail-closed assertions.

**Policy tradeoff:** This temporarily **holds automatically generated present-tense emergency warning announcements**, including genuinely new warnings, until a verified NWS event/expiration validation system is implemented. Human-authored and fact-checked breaking news remains possible via the existing custom article process. This is intentional: the current generative feed must not be trusted to independently determine that an emergency alert is currently active.

## Installation (website repository, NOT iOS)

1. **Compare** your current `scripts/generate.py` and `data/source-retirement-editor-overrides.json` with this overlay if more changes have landed since the uploaded website snapshot. This ZIP incorporates the **previous Oct 12 expired-warning overlay**; don't reapply the older ZIP on top of this one.
2. Extract the files into the root of `tc-today` (same directories), commit, push.
3. Run **Test Editorial Engine**. Check green.
4. Run **Update Treasure Coast Today** and ensure it deploys successfully. The currently published page won't change until the updated files deploy. Archive recovery may need a normal generation run to remove stale entries.
5. Check **all three affected URLs**: October 11 old slug, October 12 same-title slug, October 12 "Until 7 PM" slug. They should show the retirement page or redirect to Archive, be excluded from `archive.json`, RSS, sitemap and page cards. Check Top News/Martin/category views for stale copies.
6. Check the update run logs for `EMERGENCY ALERT SAFETY HOLD` when an unverified automatic alert is attempted. If any such claim survives, `EMERGENCY ALERT PUBLICATION BLOCKED` will stop the workflow. This is expected fail-closed behavior, not a reason to disable the validation.

NWS bulletin: https://forecast.weather.gov/product.php?issuedby=MLB&product=FFW&site=NWS

### Local tests performed

`python -m pytest -q tests/test_hometown_source_retirement.py tests/test_live_permalink_integrity.py tests/test_publisher_redirects.py tests/test_emergency_alert_publication_safety.py tests/test_expired_flash_flood_warning_retirement.py`

**44 passed.** Python source compilation also passed. This is *not* a full production/editorial generation run, and the repository has not been deployed from this environment.
