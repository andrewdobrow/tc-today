# v1.13.6.7h — Fresh Follow-up Hero Preservation / Shadow Alignment Integrity

## Problem

The Aug. 24 final-pipeline assignment-editor bakeoff exposed a remaining asymmetry in the stale-hero logic.

Sonnet 5 correctly selected a newly published WPEC report on the National Weather Service's Monday confirmation of Sunday's Port St. Lucie EF0 tornado as the St. Lucie County hero. The shadow final-alignment layer then classified that hero as stale merely because the article body referred to Sunday and swapped a city-attorney story into the hero slot.

That was not an editorial-model decision. It was a deterministic freshness-classification error.

## Root cause

Live generation and the assignment-editor shadow each carried their own copy of the stale-story test. Both tests treated any reference to one of the prior four day names as stale before considering whether the article itself contained a genuinely new current-day development.

A fresh Monday confirmation of a Sunday event therefore could be mistaken for stale coverage.

## Change

- Replaced the duplicated live/shadow stale-story logic with one shared `_category_story_is_stale()` contract.
- Preserved the existing protections against publisher timestamp re-touches of old incidents.
- Added a narrow current-day-development exception that requires BOTH:
  1. a source publication timestamp less than 24 hours old; and
  2. explicit current-day update language in the lead (for example confirmation/announcement/survey/findings language tied to the current day).
- Live category generation and the assignment-editor shadow now call the exact same stale-story function.
- No model prompt or category-fit behavior changed.

## Permanent regressions

1. A fresh Monday NWS confirmation/damage survey of a Sunday tornado is not stale.
2. A publisher re-touching an old event today without a new current-day development remains stale.
3. Exact St. Lucie shadow regression: the fresh tornado hero is preserved instead of being swapped to the Fort Pierce city-attorney card.

## Validation

- `tests/test_assignment_editor_shadow.py`: 20/20 passed.
- Broader relevant suite: 42/42 passed across assignment editor, stale hero, canonical hero freshness, category-generation containment, final category identity, and model bakeoff tests.
- Package validation: 38 modules / 119 public exports.
- Python compilation: passed.

## Rollout

Apply after v1.13.6.7g, run Test Editorial Engine, then run a natural production cycle with only the Sonnet 5 assignment-editor → Sonnet 4.5 writer shadow enabled.
