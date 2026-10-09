# Treasure Coast Today v1.13.9.108 — Section Editorial Ranking

## Why
v1.13.9.105 made county/topic decks strictly chronological. v1.13.9.106 fixed the more fundamental cross-section candidate-pool leakage by giving every section its own server-built deck. Strict chronology, however, is not the intended newsroom behavior: county/topic fronts should remain editorially ranked by importance/urgency while stale stories are prevented from dominating.

## Behavior
- Preserves v1.13.9.106 section-owned candidate pools.
- Builds each county/topic front from both the final live section placements and recent canonical archive stories for that same section.
- Ranks the active section hero + six cards using urgency/importance plus strong freshness weighting.
- Normal stories compete for up to 7 days.
- Only urgency 8–10 stories can remain from day 7 through day 14; they receive no freshness points after day 7, so genuinely new coverage normally outranks them.
- Stories older than 14 days cannot appear in the active section hero/card deck and remain available under More Stories/archive.
- Transient alerts/closures expire after 48 hours; routine Sports stories expire after 72 hours unless urgency is at least 9.
- A validated material update may legitimately refresh an older canonical. Routine `lastmod` changes do not.
- Explicit `force_hero` remains an editor override.
- The browser preserves server editorial order and no longer re-sorts section cards chronologically.
- Writes `data/section-editorial-ranking.json` for per-section ranking diagnostics.
- Bumps shared asset version to `1.13.9.108`.

## Regression coverage
- Important recent coverage can outrank a newer routine story.
- A month-old urgency-10 story is barred from the active section deck.
- A 10-day urgency-9 story can survive the extended window but is normally beaten by genuinely fresh coverage.
- A validated material update can refresh an older canonical.
- Recent canonical archive stories are added to the section candidate pool even when the current generation pass omitted them.
- The client preserves server editorial rank instead of sorting by timestamp.
- v1.13.9.106 section ownership and Dolly-style cross-section leakage protections remain enforced.

## Validation
- 16/16 direct section ranking/ownership/chronology tests passed.
- 182/182 broader relevant tests passed, including Top Stories freshness, county authority, category eligibility, canonical surface dedup, navigation/audience behavior, and v1.13.9.107 Westmoreland custom-scoop continuity.
- `python -m py_compile scripts/generate.py` passed.
- `node --check main.js` passed.
- Six legacy canonical-identity fixture tests in the extracted verification snapshot remain unavailable because that snapshot lacks root `engine.py`; they do not reach this patch's code.
