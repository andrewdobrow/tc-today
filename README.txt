TCT — Verified Oct 23 PSL Hit-and-Run Correction + Newsletter HTML Boundary Fix
==============================================================================

ROOT-PATH ZIP OVERLAY. Extract into tc-today, replace matching files, commit,
push, then run Test Editorial Engine followed by Update.

Files (exactly three production/test files plus this README):
  data/article-content-overrides.json
  scripts/prepare_membership_paywall.py
  tests/test_psl_hit_run_verified_oct23_correction.py

Verified reporting: Port St. Lucie Police Chief Leo Niemczyk identified
Eric Saint Aude, age 60, as the driver arrested in the October 9 collision
at the October 23 briefing. Charge: leaving the scene of a crash involving
serious bodily injury. Investigators still seek a second, southbound vehicle.
Source (Treasure Coast Newspapers syndicated report):
https://bluewaterhealthyliving.com/news/national-news/florida/police-officials-update-on-arrest-in-florida-hit-and-run-investigation/

The correction is attached to the EXISTING article slug, not a new publication.
It is re-applied by scripts/generate.py on every Update run before the current
membership-preparation and protected-content sync steps. The old pre-briefing
story text is replaced; existing canonical permalink, image and article
identity are preserved. The override timestamp records editorial correction
creation on October 23 (Eastern time).

The newsletter fix addresses a reproducible index-offset bug in
scripts/prepare_membership_paywall.py: article prose sanitation may change
the HTML length, but the old regex match was reused when replacing the article
body with paywall markup. That could slice through the following inline
newsletter <aside> and expose 'slot--article" aria-label=...' as text.
The code now recomputes the regex match after sanitation; if the body/slot
boundary no longer matches, it fails closed rather than slicing blindly.

Test suite checked: 52 directly related tests passed against the available
2026-10-23 reconstructed generator; the complete current GitHub checkout was
not available, so run Test Editorial Engine before Update.

IMPORTANT MERGE NOTE:
The shared data/article-content-overrides.json included here preserves six
records from the most recent AVAILABLE uploaded repository snapshot. If your
current GitHub file acquired further corrections after that snapshot, those
newer records must be merged instead of lost. The generator, archives,
custom_articles.json, workflows and existing article HTML are NOT replaced.
