# TCT v1.13.7.1i — Authoritative Custom Material-Update Transaction Preservation

## Production evidence
The v1.13.7.1h Generate News run proved that the Debevec body-recovery update survived source promotion, category selection, generation, quality guards, and forward identity stamping. It appeared as the generated hero in both Crime & Safety and Martin County. Before `write_archives()` could commit the canonical update, `suppress_authoritative_custom_incidents_from_live()` removed two live placements because the existing Aug. 29 Debevec article is an authoritative custom canonical. The v1.13.7.1h terminal material-update invariant then correctly failed the run because the selected validated update never reached the committed `material_updates` ledger.

## Failure boundary corrected
`suppress_authoritative_custom_incidents_from_live()` still removes ordinary feed duplicates of authoritative custom work, but it now distinguishes a duplicate placement from a pending canonical update transaction.

A feed/generated placement is preserved through the custom-incident lock only when all of the existing target-bound material-update authority remains valid for the exact matched custom canonical:

- semantic material update is present;
- pre-generation material-update promotion is present;
- the validated semantic decision is `update_existing_canonical` / the configured semantic update action;
- `same_real_world_event` is true;
- `material_new_update` is true;
- the semantic decision's selected canonical slug matches the matched custom canonical;
- the canonical write authorization token is valid for that exact slug.

If any of those requirements is absent or mismatched, the existing custom duplicate suppression behavior is unchanged.

The guard now emits an explicit production diagnostic when it preserves such a transaction:

`Authoritative custom incident lock preserved N validated material-update placement(s) for canonical commit`

## Regression coverage
Added a Debevec-specific regression reproducing the Sept. 1 production state with the Aug. 29 authoritative custom canonical and two generated body-recovery placements (Crime & Safety and Martin County). Both must survive the custom-incident lock when they carry valid target-bound material-update authority.

Added a negative Debevec regression proving an unapproved same-incident reprint is still removed by the custom lock.

Extended the existing canonical custom material-update integration test so the promoted/generated update must pass through the same global custom-incident lock before `write_archives()` updates the one canonical page. This covers the production ordering that v1.13.7.1h exposed.

## Validation
- `python -m py_compile scripts/generate.py` — passed
- Focused custom + published-story suite — **43 passed**
- Broader material-update / missing-person / semantic publication suite — **128 passed**
- `python scripts/validate_package.py` — **passed: 38 modules imported and 122 public exports verified**
- Exact Test Editorial Engine pytest command:
  `python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`
  — **1082 passed, 0 failed**, 44 existing datetime deprecation warnings

## Production acceptance standard
This patch is validated against the newly exposed custom-lock failure boundary, but it is not declared production-proven until Generate News demonstrates the selected Debevec material update reaches a committed canonical update. v1.13.7.1h's terminal invariant remains active: a selected validated material update that disappears before commit must fail the workflow rather than silently publish stale coverage.
