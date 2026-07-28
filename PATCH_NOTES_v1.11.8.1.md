# TCT v1.11.8.1 — Retrospective Timeline Coherence Gate

## Scope

This is a narrow observe-only quality increment over v1.11.8.0. It does not split,
merge, suppress, rank, publish, redirect, or otherwise mutate persistent stories or
live coverage. Follow-up activation remains disabled.

## Root cause

Retrospective follow-up analysis previously trusted two fields that can be contaminated
inside an incoherent persistent story:

- the shared `story_id`; and
- overlap with the story's current `canonical_title`.

A newer unrelated entry can become the canonical title, producing perfect canonical
headline overlap with itself. That allowed unrelated timeline pairs to be labeled
high-confidence or activation-eligible even when their prior and newer articles shared
no independent event identity.

The production examples were:

- Indian River County firefighter Geoffrey Lang coverage followed by an unrelated Palm
  Beach County cat-and-hamster house-fire rescue; and
- a Sebastian apartment shooting followed by Geoffrey Lang's death coverage.

## Independent transition identity

Every retrospective milestone transition now has to independently qualify through at
least one deterministic anchor:

- exact safe source-article URL identity;
- exact event key;
- strong pairwise title continuity with at least three shared discriminative tokens; or
- matching semantic event family corroborated by pairwise title continuity and shared
  discriminative tokens.

Canonical-title overlap remains visible as context but cannot qualify a transition.
The persisted story ID is explicitly treated as untrusted evidence during this check.

## Incoherent timeline quarantine

An unanchored retrospective transition now:

- receives `timeline_identity_unanchored` as a blocking conflict;
- is capped below the high-confidence threshold;
- is excluded from activation-eligible evidence;
- is marked `timeline_incoherent: true`; and
- places its persistent story into the new `incoherent_stories` review queue.

New retrospective report fields:

```text
identity_anchor_rejected_count
incoherent_transition_count
incoherent_story_count
incoherent_stories
```

Each candidate also reports:

```text
identity_anchor_qualified
identity_anchor_codes
shared_title_tokens
timeline_incoherent
```

The production summary prints the incoherent transition and story counts.

## Production replay

Replaying the latest 562-story production registry produced:

- 6 retrospective milestone candidates;
- 3 anchored high-confidence candidates;
- 1 activation-eligible candidate;
- 2 incoherent transitions across 2 story timelines.

The two incoherent transitions are the exact Geoffrey Lang/house-fire and Sebastian
shooting/firefighter-death regressions. The legitimate missing-child recovery remains
the only activation-eligible candidate through exact source-article identity. The
Martin County hoarding timeline remains coherent and reviewable.

## Versioning

- Engine: `1.11.8.1`
- Release: `retrospective-timeline-coherence-gate`
- Relationship diagnostics: `1.5`
- Observability schema: `15`

## Validation

- Focused follow-up and version regressions: 19 passed.
- Workflow-equivalent test suite: 373 passed.
- Package validation: 29 modules and 98 public exports.
- Existing warnings: 17 `datetime.utcnow()` deprecation warnings.
- GitHub Actions and production have not yet run with v1.11.8.1.
