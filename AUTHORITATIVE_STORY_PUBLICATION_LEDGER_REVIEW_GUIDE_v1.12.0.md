# v1.12.0 Production Review Guide

After applying the overlay, run **Test Editorial Engine**, then the production
workflow.

## Required test result

All workflow-equivalent tests must pass.

## Required production reports

### `data/canonical-publication-ledger.json`

Confirm:

- `passed` is `true`
- `remaining_identity_conflicts` is empty
- `write_barrier_holds` in the forward-publication report contain no unexpected
  unrelated-story matches
- `generic_same_event_edges` reflects only clearly corroborated historical pairs

### `data/global-incident-identity-contract.json`

Confirm:

- `passed` is `true`
- `duplicate_incident_group_count` is `0`
- `active_redirect_source_count` is `0`

### `data/live-category-canonical-contract.json`

Confirm every topic and county category passes, especially Indian River County and
St. Lucie County.

## Live checks

The Indian River County category must expose one Geoffrey Lang canonical article.
Every other Lang URL must redirect to it.

The St. Lucie County category must expose one Glades Cut Off Road traffic-light
article. The July 30 duplicate must redirect to the July 29 canonical.

## Update check

For any story logged as `update_existing`, read its first paragraph without looking
at the headline. It must explain both the original issue and what changed. A failed
update should leave the prior canonical article intact rather than create a new URL.

## Major-update policy

This release does not automatically mint separate major-update permalinks. An
automated development must update the established canonical or be held. A future
separate-link contract must require an explicit qualifying milestone, a parent
publication ID and a self-contained contextual lead before activation.
