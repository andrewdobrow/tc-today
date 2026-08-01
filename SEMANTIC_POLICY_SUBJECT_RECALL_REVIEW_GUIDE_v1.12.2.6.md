# Semantic Policy-Subject Recall Review Guide — v1.12.2.6

## Apply

Apply this repository-root overlay on top of **v1.12.2.5**.

## Production expectation

On the next run, the recent-archive semantic repair should nominate the Martin County shark-fishing articles for Claude. The report should show the selected candidate with:

```json
{
  "structured_conflict_override": true,
  "structured_conflict_override_tier": "policy_subject_continuity"
}
```

Claude must still determine whether each later report is:

- the same event with no material update, which produces a canonical redirect; or
- the same event with a material update, which preserves the canonical URL and routes the update; or
- a genuinely different proceeding.

## Inspect

Review:

- `data/semantic-publication-gate.json`
- `data/archive.json`
- `data/editorial_story_registry.json`
- the complete workflow log

Confirm that the August 1 URL is no longer an independent active article only if Claude returns `duplicate_use_existing_canonical`. If Claude finds a material state-preemption development, the correct result is `update_existing_canonical`, not automatic deletion.

Also check the July 30 shark-fishing article because it shares the same policy-subject recall pattern.

## Regression scope

The release includes exact production-headline regressions for the July 29, July 30, and August 1 shark-fishing reports, plus a negative-control test involving an unrelated Martin County noise ordinance.
