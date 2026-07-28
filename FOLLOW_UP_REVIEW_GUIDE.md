# Follow-Up Candidate Review Guide

After the first successful v1.11.6.0 production run, open:

```text
data/editorial_observability.json
```

The follow-up report now has two evidence streams:

```text
follow_up_detection.examples
follow_up_detection.retrospective.examples
```

## Current-run candidates

`follow_up_detection.examples` contains milestones detected while a new article is being processed.

Review:

- `headline`
- `current_relationship`
- `candidate_story_id`
- `candidate_confidence`
- `candidate_milestones`
- `candidate_reason_codes`
- `candidate_trace`

The current conservative relationship remains authoritative. These candidates do not change grouping.

Beginning with v1.11.8.0, current-run candidates must also contain
`identity_anchor_qualified` in `candidate_reason_codes`. A milestone word and generic
fact overlap are not identity. Qualification requires either an exact event key or a
corroborated combination of location, agency, named entity, event type, and strong
title/fact continuity.

The summary field `unanchored_candidate_suppressed_count` shows how many legacy or
intermediate candidates were withheld because they lacked that evidence.

## Retrospective timeline candidates

`follow_up_detection.retrospective.examples` examines transitions already stored inside persistent story timelines.

Each example includes:

- `story_id` and `story_title`
- `prior_article`
- `newer_article`
- `milestones`
- `matched_phrases`
- `confidence`
- `blocking_conflicts`
- `activation_eligible`
- `reason_codes`
- `candidate_trace`

The summary also reports:

- `stories_with_timelines`
- `timeline_entries_examined`
- `transitions_examined`
- `candidate_count`
- `high_confidence_candidate_count`
- `activation_eligible_candidate_count`
- `milestones`
- `blocking_conflicts`
- `excluded_entry_count`
- `exclusion_reasons`

## Blocking conflicts

A candidate remains visible for review but cannot count as activation evidence when any blocking conflict is present.

Current conflicts include:

- `same_timestamp_order_uncertain`: migrated or batch-added entries have identical timestamps, so chronology is not trustworthy.
- `weak_title_continuity`: the newer title has insufficient overlap with both the prior title and the story's canonical title.
- `multiple_terminal_milestones`: one title appears to contain several incompatible terminal stages.

## Entries excluded from activation evidence

The retrospective pass excludes:

- social-media entries;
- low-value explainers, opinion, live-update and generic video/photo titles;
- titles too thin to establish a reliable transition.

Excluded entries do not establish known milestones and cannot suppress later legitimate evidence.

## Phrase-aware milestone rules

Observe-only milestone matching now requires meaningful words or phrases.

Examples:

- `breaks ground` can indicate an opening or construction milestone;
- `breaks down` does not;
- `cancels the route` can indicate closure;
- `happy ending` does not;
- `wins the election` can indicate an election result;
- a generic sports use of `wins` does not.

## Review order

Review candidates in this order:

1. `activation_eligible: true`;
2. confidence of 0.85 or higher;
3. recovery, arrest, sentencing and formal approval milestones;
4. candidates with chronology support and no conflicts;
5. blocked candidates to decide whether the conflict is a data-quality issue or a false match.

Classify each example as:

1. true follow-up;
2. duplicate coverage of the same milestone;
3. related but distinct story;
4. false candidate;
5. chronology cannot be determined.

## Activation threshold

Do not activate follow-up grouping until production evidence includes:

- at least 20–30 high-confidence candidates;
- at least 95% manually verified precision;
- zero location, person, agency or event-type identity conflicts;
- no unrelated story merges;
- stable results across two or three production runs;
- a permanent regression test for every false positive.

v1.11.8.0 remains fully observe-only for candidate activation. It does not activate
broader follow-up grouping or modify URLs, ranking, suppression, hero selection or
publication based on candidate diagnostics.
