# TCT v1.11.6.0 — Retrospective Follow-Up Observability

## Purpose

The first follow-up candidate rollout completed safely but returned zero candidates even though the persistent registry contained obvious historical progression, including a missing-child alert followed by a safe recovery update.

The original observe-only layer evaluated milestones only as an incoming article arrived. Once both stages already existed in the registry, it could no longer report the transition. This release adds a retrospective timeline pass while preserving every live editorial decision.

## Behavior

This release does **not** change:

- story grouping;
- canonical URLs;
- duplicate suppression;
- ranking;
- hero selection;
- publication eligibility;
- activation behavior;
- custom article handling.

The retrospective pass reads existing persistent story timelines and writes diagnostics only.

## Retrospective report

`data/editorial_observability.json` now includes:

```json
"follow_up_detection": {
  "candidate_count": 0,
  "retrospective_candidate_count": 0,
  "retrospective_high_confidence_candidate_count": 0,
  "retrospective_activation_eligible_candidate_count": 0,
  "retrospective": {
    "mode": "retrospective_observe_only",
    "publication_behavior_changed": false,
    "stories_with_timelines": 0,
    "timeline_entries_examined": 0,
    "transitions_examined": 0,
    "candidate_count": 0,
    "high_confidence_candidate_count": 0,
    "activation_eligible_candidate_count": 0,
    "milestones": {},
    "blocking_conflicts": {},
    "excluded_entry_count": 0,
    "exclusion_reasons": {},
    "examples": [],
    "review_ready": false,
    "enforcement_ready": false
  }
}
```

Each retrospective example contains the prior and newer timeline articles, the novel milestone, exact matched phrases, confidence, reason codes, blocking conflicts and an activation-evidence flag.

## Phrase-aware milestones

Observe-only milestone matching is now phrase-aware.

The following false-positive paths are closed:

- bare `breaks` no longer means opening;
- `expert breaks down` cannot trigger an opening milestone;
- bare `ending` no longer means closure;
- `happy ending` cannot trigger closure;
- bare `wins` no longer means an election result;
- bare `passed` no longer means government approval.

Supported phrases include `breaks ground`, `cancels the route`, `wins the election`, `safely located`, `found safe`, formal approval language and other explicit lifecycle progression.

The live enforced follow-up vocabulary is unchanged. The stricter phrase rules apply to observe-only candidate evidence.

## Evidence quality controls

The retrospective pass excludes social-media and low-value timeline entries from activation evidence. It also blocks candidates when:

- timeline entries have the same timestamp and chronology is uncertain;
- title continuity is too weak;
- multiple incompatible terminal milestones appear together.

Blocked candidates remain visible for manual review.

## Production log indicator

The engine summary now prints:

```text
Follow-up candidates:    current=N / retrospective=N
Activation evidence:     N retrospective candidate(s); observe-only
```

These are the indicators to inspect after each production run.

## Replay against the latest production registry

A local replay over the supplied production registry found:

- 151 stories with multi-entry timelines;
- 380 timeline entries examined;
- 221 eligible transitions examined;
- 4 retrospective candidates;
- 3 high-confidence candidates;
- 1 clean activation-evidence candidate;
- milestones: arrest, court action, identified and recovery.

The clean candidate was the missing-child alert followed by the child being safely located. Three other candidates remained blocked by same-timestamp chronology uncertainty, with one also showing weak title continuity.

## Versioning

- Engine version: `1.11.6.0`
- Engine release: `retrospective-follow-up-observability`
- Observability schema: `13`
- Relationship diagnostics version: `1.4`
- Package version: `1.11.6.0`

## Validation

- Focused relationship, lifecycle and observability tests: 26 passed.
- Full CI-equivalent suite: 365 passed.
- Package validation: 29 modules and 98 public exports.
- Existing warnings: 18 `datetime.utcnow()` deprecation warnings.
- GitHub Actions and production were not run with this release during local validation.
