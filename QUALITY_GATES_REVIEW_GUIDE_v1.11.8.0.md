# v1.11.8.0 Production Review Guide

After applying the overlay over v1.11.7.4, run the normal production workflow.

## 1. Follow-up evidence

Open `data/editorial_observability.json` and review:

```text
follow_up_detection.candidate_count
follow_up_detection.high_confidence_candidate_count
follow_up_detection.unanchored_candidate_suppressed_count
follow_up_detection.examples
```

Every current-run example must contain `identity_anchor_qualified` in
`candidate_reason_codes`. No example should show all of the following as false:

```text
Location match
Agency match
Entity match
```

The production console should print:

```text
Follow-up candidates: current=N / retrospective=N / unanchored_suppressed=N
```

Candidate activation remains off.

## 2. Sports section

Review the Sports hero and cards on the live category page. Acceptable subjects include
actual teams, athletes, games, results, tournaments, signings, drafts, athletic awards,
and sports facilities.

The following must not appear as Sports:

- museum or art exhibitions;
- police or school-supply community events;
- unrelated festivals and general Things To Do coverage;
- crime, government, business, or obituary stories that merely contain a loose sports word.

When no valid current Sports story exists, archive recovery is preferable to an
off-topic live story.

## 3. Category hero time

Open each category filter and inspect the hero footer.

Newly published articles should show their actual TCT publication time. A feed that
supplied only a date may show a date label, but should not show `12:00 AM` unless TCT's
own `first_published` receipt genuinely records midnight.

Useful checks:

- current story: `3:45 PM ET`;
- previous-day story: `Yesterday, 3:45 PM ET`;
- date-only legacy story: `Jul 27, 2026`.

## Files to collect

For the first production review, provide:

1. the complete workflow log;
2. `data/editorial_observability.json`;
3. `data/category-generation-report.json`;
4. `data/story-regression-report.json`;
5. a screenshot of any category hero that still shows an incorrect time.
