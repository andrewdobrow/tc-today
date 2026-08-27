# v1.13.6.7p Review Guide

Apply this overlay directly to the fresh post-6.7o repository. It is root-ready; do not place it inside an extra directory.

Expected Test Editorial Engine result:
- **1,013 tests** in the CI-equivalent suite (excluding the workflow's two standard ignored files)
- zero failures
- package validation: **38 modules / 122 public exports**

## Production validation priorities

Run one normal production cycle after the test workflow is green, then inspect the semantic publication and homepage authority diagnostics before restarting any model bakeoff.

The run should demonstrate all of the following:
- A legitimate same-canonical material update keeps the existing permalink while the live headline/body and update freshness advance together.
- No stale `permalink_origin_headline` is restored as the live headline.
- Terminal first-pass HOLDs receive at most one focused resolution pass. Clear unrelated candidates may resolve NEW; same-event candidates route to UPDATE/DUPLICATE; unresolved cases remain HOLD.
- `data/semantic-publication-gate.json` records terminal resolution counters and final per-source authority outcomes.
- Redirect-backed or story-equivalent homepage candidates are canonicalized before Top Stories ranking and cannot survive as independent duplicate placements after final binding.
- Assignment-editor shadow output does not include a source that production terminal authority held.

## Bakeoff status

Do **not** score a new Sonnet 5 assignment-editor vs. Sonnet 4.5 writer bakeoff until this production validation is clean. The last meaningful bakeoff remains **Sonnet 5 assignment editor: 1 win / 0 losses / 1 tie**.
