# TCT v1.13.6.5b — Category Routing Integrity Hotfix

## Problem

The Aug. 22 model bake-off exposed an invalid Things To Do source packet. A Martin County animal-hoarding recovery story and multiple Palm Beach County/Jupiter/Sunrise stories reached the Things To Do generator even though they were not valid Treasure Coast Things To Do candidates.

Root cause:

1. `classify_stories()` silently truncated the classification universe to the first 120 unique feed stories.
2. Stories outside that cap could enter topic-category filtering through broad keyword scoring.
3. Local topic categories did not have one shared hard Treasure Coast locality boundary for every card candidate.
4. Things To Do had no enforced semantic eligibility contract, so generic words such as community/weekend/event-adjacent language could score unrelated stories.
5. A category could still spend a Claude call even when deterministic hero eligibility found no valid lead.

## Fix

- Classify the complete feed universe in bounded batches of 120 instead of truncating globally at 120.
- Preserve exact-input classification cache hits; only cache misses are sent to Claude.
- If a classification batch fails, those stories remain unclassified and are blocked from topic-category generation rather than using keyword fallback.
- Require deterministic Treasure Coast locality for all local topic beats: Local Government, Crime & Safety, Business & Development, Sports, and Things To Do.
- Add an enforced Things To Do contract requiring a genuinely attendable local event/activity/dining/recreation/cultural program.
- Reject animal-welfare/crime/government stories that lack an explicit event/activity focus even if a stale/bad classifier label says `things_to_do`.
- Add Things To Do zero-candidate fast recovery so Claude is skipped when there is no deterministic local event/activity lead.
- Bump only the Things To Do category-generation cache contract version; unrelated category caches remain reusable.

## Exact production regression

A permanent regression reconstructs the contaminated source pool from the bake-off:

- Palm Beach Food & Wine Festival
- Morikami Obon Weekend in Delray Beach
- Loggerhead Triathlon in Jupiter
- Monster Jam in Sunrise
- Palm Beach County Habitat home story
- Palm Beach Gardens NASCAR nonprofit contest
- Martin County animal-hoarding recovery

The test deliberately labels every row `things_to_do`. Deterministic routing must still return an empty Things To Do live source pool.

## Validation

- workflow-equivalent pytest: **919 passed**
- existing warnings: **43** (`datetime.utcnow()` deprecations)
- package validation: **37 modules / 119 exports — PASS**
- generator runtime hotfix guard: **PASS**
- false-jurisdiction source guard: **PASS**

## Production verification

Run **Update Treasure Coast Today** normally with the model bake-off disabled for this validation run.

Expected classification log now resembles:

`Story classification: X cache hit(s), Y Claude-classified across N batch(es), 0 unclassified/blocked (...)`

For local topic sections, any rejected outside-area or unclassified candidates are explicitly logged:

`Category routing gate: rejected X outside-Treasure-Coast and Y unclassified ... source(s)`

Things To Do must never send the Martin County hoarding recovery story or Palm Beach/Jupiter/Sunrise event stories to Claude. If there is no valid current Things To Do source, the generator should use verified archive recovery instead.
