# Persistent Timeline Coherence Integrity Review Guide — v1.13.0.4

## Required workflow

1. Run **Test Editorial Engine**.
2. Confirm package validation and the complete pytest suite pass.
3. Run **Update Treasure Coast Today**.
4. Review the reports listed below before beginning another increment.

## Required reports

- `data/editorial_story_registry.json`
- `data/editorial_observability.json`
- `data/persistent-story-identity-integrity.json`
- `data/story-regression-report.json`
- `data/category-generation-report.json`

## Acceptance criteria

- Persistent-story identity integrity passes.
- `timeline_coherence_violation_count` is `0`.
- `remaining_timeline_coherence_violations` is `0`.
- The Belle Glade crash does not share a story ID with the Martin County tax article.
- The cat-and-hamster rescue does not share a story ID with Geoffrey Lang coverage.
- The Loxahatchee Groves shooting does not share a story ID with the officer DUI story.
- Firefighter hazing, Oxmoor Terrace and double-execution timelines remain intact.
- A contaminated story ID cannot produce `registry_skip_story_already_published` suppression.

## Expected observability behavior

The first production run may report registry health as `repaired`, which keeps
activation in shadow. A subsequent clean run should report registry health as
`clean` with zero timeline violations.
