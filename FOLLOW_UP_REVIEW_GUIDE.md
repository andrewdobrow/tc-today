# Follow-Up Candidate Review Guide

After the first successful v1.11.5.0 production run, open:

```text
data/editorial_observability.json
```

Then inspect:

```text
follow_up_detection.examples
```

## Fields

- `headline`: incoming candidate headline.
- `current_relationship`: the relationship the live conservative engine used.
- `candidate_story_id`: existing persistent story that may deserve the update.
- `candidate_confidence`: deterministic confidence from 0 to 1.
- `candidate_milestones`: lifecycle advancement detected in the incoming article.
- `candidate_reason_codes`: continuity anchors and conflicts.
- `candidate_trace`: full explainable scoring trace.

## Priority order

Review candidates in this order:

1. confidence of 0.85 or higher;
2. exact-event-key candidates;
3. candidates with agency and entity continuity;
4. candidates currently classified as `new_story`;
5. candidates with `event_type_conflict` or `agency_conflict`.

## What should eventually be activated

A future enforcement patch should activate only patterns that show near-perfect precision in production, such as:

- missing person → safely located;
- rescue or investigation → arrest or charges;
- arrest → indictment, trial or sentencing;
- fire → contained or resolved;
- proposal → formal approval when the same project and government body are explicit.

Broad semantic similarity must never be sufficient by itself.
