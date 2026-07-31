# Event Identity Authority Boundary Review Guide — v1.12.0.7

## Purpose

Verify that the editorial engine can discover possible cross-source relationships without allowing fuzzy similarity to overwrite an established Treasure Coast Today permalink.

## Required production reports

Review:

- `data/event-identity-authority.json`
- `data/cross-source-update-identity.json`
- `data/canonical-publication-ledger.json`
- `data/story-regression-report.json`
- `data/editorial_observability.json`
- `data/archive.json`

## Required authority results

In `event-identity-authority.json`:

- `passed` must be `true`.
- `summary.unauthorized_destructive_count` must be `0`.
- Every row with `final_publication_action` equal to `update_existing`, `canonical_bound_before_generation`, or `reuse_existing_canonical_before_slug_creation` must have:
  - `identity_outcome: same_event_verified`
  - `write_authorized: true`
  - a nonempty `proof_type`
- Rows classified as `possible_relationship` must remain candidate-only and must not inherit a canonical story ID or update route.

A zero verified-write count is acceptable when the live feeds contain no proven updates.

## Evidence review

For every verified cross-source identity, confirm the proof is based on one of the following:

- exact normalized source URL;
- registry-certified persistent story ID;
- exact structured incident or known event key with independent corroboration;
- same participant plus same precise location and compatible event family;
- same participant or precise location plus multiple distinctive incident facts;
- same governing body plus the same specific policy subject and multiple distinctive facts.

Do not accept county, agency, general crime type, broad drug terminology, official quotations, publisher names or headline similarity as standalone proof.

## Immutable identity review

Sample newly archived records and confirm `event_identity` exists. It should describe the source event as first published and remain unchanged when an article is updated. Names and locations appearing only in TCT background prose must not become later identity anchors.

## Final publication review

For each updated existing page:

1. Confirm the incoming source belongs to the same real-world event.
2. Confirm the canonical slug remained stable.
3. Confirm `first_published` did not change.
4. Confirm the prior page was not replaced by an unrelated article.
5. Confirm the update lead explains both the original event and the new development.

## Regression signatures that must remain absent

- Fentanyl sentencing mapped to the Sebastian decomposed-body article.
- Child sexual-battery arrest mapped to the Port St. Lucie roof chase.
- Police-union coverage mapped to an unrelated impersonation case.
- Separate I-95 crashes merged because they share a highway and event family.
- Separate lawsuits merged because they share legal terminology or an institution.

## Runtime

Candidate blocking must remain active. Archive reconciliation should evaluate only a small fraction of all possible archive pairs, rather than performing an unrestricted quadratic scan.
