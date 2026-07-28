# TCT v1.11.8.0 — Identity-Anchored Follow-Ups, Sports Relevance, and Hero Time Repair

## Scope

This is a focused quality increment over v1.11.7.4. It does not activate broader
follow-up grouping and does not change canonical URLs, custom article authority,
ranking enforcement, duplicate suppression, or county membership behavior.

## Current-run follow-up evidence

Current-run candidate diagnostics now require `identity_anchor_qualified`.
Milestone vocabulary and generic fact overlap can no longer create review evidence by
themselves. Qualification requires one of the following:

- an exact event-key anchor;
- location plus agency;
- location plus a named entity;
- agency plus entity with meaningful title continuity; or
- a named agency/entity plus event-type continuity and very strong title/fact overlap.

Sparse events remain separate stories. Unanchored candidates are withheld from the
current-run examples and counted in:

```text
follow_up_detection.unanchored_candidate_suppressed_count
```

The production summary prints the same count. Retrospective timeline analysis is
unchanged and remains observe-only.

## Deterministic Sports relevance

A classifier label is no longer sufficient to make a story eligible for Sports.
Sports heroes and cards now require concrete athletic evidence such as:

- a sport, team, league, athlete, coach, or player role;
- a game, match, race, tournament, championship, season, score, result, or roster move;
- an athletic award, draft, signing, or recruiting event; or
- a recognized sports facility or organization.

This blocks the production regressions involving a Vero Beach museum exhibition and a
Sebastian Police back-to-school event while preserving St. Lucie Mets coverage, local
high-school results, and athlete awards.

## Category hero timestamps

Category heroes now use the article archive's `first_published` value as the
publication receipt when available. This is the actual time the article first appeared
on TCT.

When a source exposes only a date or a synthetic exact-midnight timestamp, the page
shows a calendar date such as `Jul 27, 2026` instead of falsely displaying `12:00 AM`.
Existing relative labels such as `Yesterday, 3:45 PM ET` remain supported.

## Versioning

- Engine: `1.11.8.0`
- Release: `identity-anchored-followups-sports-and-hero-time`
- Relationship diagnostics: `1.5`
- Observability schema: `14`

## Validation

- Focused follow-up, Sports, timestamp, and version tests: 29 passed.
- Workflow-equivalent test suite: 369 passed.
- Package validation: 29 modules and 98 public exports.
- Existing warnings: 17 `datetime.utcnow()` deprecation warnings.
- GitHub Actions and production have not yet run with v1.11.8.0.
