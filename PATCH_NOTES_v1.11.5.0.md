# TCT v1.11.5.0 — Follow-Up Candidate Observability

## Purpose

This is the next Phase B production-readiness increment after the stable v1.11.4.9.3 run.

The latest production observability processed 181 candidates and recorded 167 `same_event` decisions, 14 `new_story` decisions and 0 `follow_up` decisions. A zero count may be correct for a quiet cycle, but it is not enough evidence to safely broaden follow-up grouping. This release adds an observe-only candidate layer so production can reveal which current decisions contain credible lifecycle advancement signals.

## Behavior

This release does **not** change publication, story grouping, canonical URLs, ranking, duplicate suppression or activation behavior.

The existing conservative relationship result remains authoritative. In parallel, the engine records a follow-up candidate when an incoming article contains a milestone not already present in a plausible existing story and has sufficient identity continuity.

Candidate signals include:

- exact event-key continuity;
- location continuity;
- agency continuity;
- event-type continuity;
- durable entity continuity;
- headline continuity;
- fact continuity;
- a novel lifecycle milestone.

Hard location and casualty contradictions remain disqualifying. Agency or event-type conflicts are reported as diagnostics but remain blocked from live grouping.

## Milestones

The enforced relationship engine keeps its existing conservative public-safety and legal milestone set.

The observe-only layer additionally recognizes high-value local-news milestones such as:

- approval or adoption;
- rejection or denial;
- opening, launch or groundbreaking;
- closure or cancellation;
- election result;
- funding or grant award.

These additional milestone types are diagnostic only in this release.

## Observability

`data/editorial_observability.json` now includes:

```json
"follow_up_detection": {
  "mode": "observe_only",
  "publication_behavior_changed": false,
  "candidate_count": 0,
  "high_confidence_candidate_count": 0,
  "current_relationships": {},
  "milestones": {},
  "reason_codes": {},
  "examples": [],
  "enforcement_ready": false,
  "enforcement_readiness_reason": "..."
}
```

Each example includes the incoming headline, current relationship, candidate story ID, confidence, novel milestones, reason codes and a deterministic trace.

## Review contract for the next production run

Review every high-confidence candidate, especially candidates currently labeled:

- `same_event`: possible same-key lifecycle advancement;
- `new_story`: possible cross-URL or sparse-event follow-up.

Classify each example as:

1. true follow-up;
2. duplicate coverage of the same milestone;
3. related but distinct story;
4. false candidate.

Only after real production examples are reviewed should a later release activate a narrow allowlist of follow-up patterns.

## Versioning

- Engine version: `1.11.5.0`
- Engine release: `follow-up-candidate-observability`
- Observability schema: `12`
- Relationship engine diagnostics version: `1.3`

## Validation

- Package validation: 29 modules and 98 public exports.
- Focused relationship/observability regressions: 19 passed.
- CI-equivalent test command used by both workflows: 354 passed.
- Existing warnings: 17 `datetime.utcnow()` deprecation warnings.
- The two legacy standalone-engine test files remain excluded by the repository workflows because the repository does not contain their historical root `engine.py` fixture target.
