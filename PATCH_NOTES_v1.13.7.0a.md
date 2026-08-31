# TCT v1.13.7.0a — Missing-Person Canonical Incident Anchor Authority

## Purpose

Critical canonical-integrity hotfix. Homepage Editorial Ranking v1.13.7.0 remains shadow-only and is not changed by this patch.

v1.13.6.8l did not provide durable enough canonical continuity for named missing-person stories. Its matching path successfully handled the first Debevec follow-up that retained the full name `Michael Anthony Debevec II`, but a subsequent publisher rewrite shortened the subject to `Michael Debevec` and used movement/context copy such as `Michael Debevec visited...` rather than an explicit `searching for Michael...` construction. The previous matcher could therefore extract no shared person and allowed the same incident to acquire another generated permalink.

## Root cause

The authoritative-custom missing-person protection was still an ad-hoc per-run comparison. The canonical custom article did not own a durable structured incident key before publication/slug creation. Normal publisher name drift could therefore defeat the matcher before the publication ledger had an independent identity authority.

The earlier custom lock also discarded a matched publisher source immediately. That meant richer later reporting could not reach the normal material-update decision even when identity had been proven.

## Changes

### Stable named missing-person incident anchor

`tct_engine.incident_identity` now emits a deterministic structured key for an unambiguous named missing-person subject:

`missing-person:<first-name>-<surname>`

For the production regression this is:

`missing-person:michael-debevec`

The key is deliberately stable across middle-name and suffix loss, including:

- `Michael Anthony Debevec II`
- `Michael Debevec`

It requires missing-person context and a single plausible named subject. It is not a general name-only merge rule.

### Durable custom identity persistence

Authoritative custom archive rows are enriched before recovery/ranking/publication-ledger construction with:

- `incident_anchor_key`
- `durable_custom_identity_key`

For Debevec:

- `incident_anchor_key = missing-person:michael-debevec`
- `durable_custom_identity_key = missing-person|michael-debevec`

This lets the canonical custom permalink own the incident before a later publisher source can mint a new slug.

### Unified missing-person alias evidence

The unified incident resolver now treats first-name + surname as a conservative subject alias when:

- both records are missing-person incidents;
- one report uses the full name and another drops middle names/suffixes;
- there is no competing explicitly extracted person.

Different named missing people still fail closed.

### Proven incident routes to the existing custom canonical

Once a later publisher source is proven to be the same authoritative custom incident, `write_archives()` no longer drops it immediately. Instead it binds the source to the existing custom canonical and sends it through the normal material-update path.

Result:

- material new facts -> update the existing custom permalink in place;
- no material new facts -> suppress the publisher copy;
- the same proven incident -> cannot mint another permalink.

Expected log marker:

`AUTHORITATIVE CUSTOM INCIDENT ROUTE: binding feed source ... -> <existing custom slug>`

### Existing escaped duplicates

Canonical cleanup now recognizes both observed Aug. 30 Debevec escape variants as the same structured incident and consolidates them to the Aug. 29 custom canonical. Existing redirect behavior remains permanent/noindex-safe.

## Regression coverage

The test suite includes the exact production drift where:

- original custom copy uses `Michael Anthony Debevec II`;
- later publisher copy says `Michael Debevec visited...`;
- both sequential Aug. 30 duplicate permalink forms resolve to the Aug. 29 custom canonical;
- the publication ledger resolves `incident:missing-person:michael-debevec` before new-slug authority;
- different named missing people remain distinct.

## Validation

Package validation:

- 38 modules imported
- 122 public exports verified

CI-equivalent pytest suite was run in two deterministic halves after the single-process runner repeatedly timed out in the harness despite no test failure:

- first half: 514 passed / 0 failed / 17 warnings
- second half: 536 passed / 0 failed / 27 warnings
- total: **1,050 passed / 0 failed / 44 warnings**

Focused missing-person suite: **20 passed / 0 failed**.
