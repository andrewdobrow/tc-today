# Registry Fixed-Point Preflight Review Guide — v1.13.1.1

## Required workflow

1. Apply the overlay to the current repository.
2. Run **Test Editorial Engine**.
3. Confirm the `Normalize persistent story registry` step runs before package
   validation and pytest.
4. Run **Update Treasure Coast Today** after the test workflow passes.

## Acceptance criteria

- The complete pytest suite passes.
- `test_repaired_production_registry_is_idempotent` passes.
- Registry preflight reports `verification_clean: true`.
- A second repair pass reports no changes.
- `remaining_source_identity_groups` is `0`.
- `remaining_unified_incident_groups` is `0`.
- `remaining_incident_identity_groups` is `0`.
- `remaining_timeline_coherence_violations` is `0`.
- The production commit contains the normalized registry when preflight makes a
  repair.

## Reports to provide after production

- Complete workflow log
- `data/editorial_story_registry.json`
- `data/editorial_observability.json`
- `data/persistent-story-identity-integrity.json`
- `data/story-regression-report.json`
