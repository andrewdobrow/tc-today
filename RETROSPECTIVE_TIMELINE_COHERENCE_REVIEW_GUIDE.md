# v1.11.8.1 Retrospective Timeline Coherence Review Guide

After applying the overlay over v1.11.8.0, run the normal production workflow.

## Expected console output

The editorial summary now includes:

```text
Timeline coherence: N incoherent transition(s) across N story timeline(s)
```

The count is diagnostic only. No live story grouping or publication behavior is
changed by this patch.

## Review `data/editorial_observability.json`

Open:

```text
follow_up_detection.retrospective
```

Review these fields:

```text
candidate_count
high_confidence_candidate_count
activation_eligible_candidate_count
identity_anchor_rejected_count
incoherent_transition_count
incoherent_story_count
incoherent_stories
examples
```

Every activation-eligible retrospective example must have:

```text
identity_anchor_qualified: true
timeline_incoherent: false
blocking_conflicts: []
```

An incoherent example should contain:

```text
identity_anchor_qualified: false
timeline_incoherent: true
timeline_identity_unanchored
```

## Permanent production regressions

The following transitions must be blocked from high-confidence and activation evidence:

1. Geoffrey Lang/firefighter death coverage → Palm Beach County cat-and-hamster house-fire rescue.
2. Sebastian apartment shooting/no injuries → Geoffrey Lang firefighter death coverage.

The following must remain valid:

1. West Palm Beach missing 10-year-old report → the child safely located in Tennessee.

For the valid missing-child transition, the expected identity anchor is:

```text
exact_source_article_identity
```

## Interpretation

`incoherent_stories` is a registry-review queue, not an automated repair queue. Do not
manually merge or split a story solely because it appears there. Review the listed
prior/newer article pair, source URLs, event keys, and title anchors first.

Follow-up enforcement must remain off. This patch only improves evidence quality.

## Files to collect

Provide after the first production run:

1. the complete workflow log;
2. `data/editorial_observability.json`;
3. `data/editorial_story_registry.json`; and
4. `data/story-regression-report.json`.
