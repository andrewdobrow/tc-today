# TCT v1.13.3.3 — Deterministic Test / Runtime State Separation

This is a CI reliability correction. It makes the separation between immutable
regression tests and mutable production registry state explicit.

## Root cause of the v1.13.3.2 failure

The previous release stopped pytest from pinning *numeric* production story IDs,
but one regression still read the current production registry and required a
historical CBS12 source URL to remain in a story timeline forever. Production
registry compaction/consolidation is allowed to discard or normalize historical
evidence, so the test failed even though the deterministic identity behavior it
was meant to protect remained covered by synthetic regressions.

The architectural error was broader: deterministic pytest tests were still allowed
to assert historical facts about mutable runtime state.

## Changes

- No pytest regression may directly read `data/editorial_story_registry.json`.
- Historical production incidents remain protected by deterministic synthetic or
  frozen-input tests, rather than by assumptions about whichever records happen
  to remain in the live registry today.
- Removed four live-registry smoke assertions whose behavior is already covered by
  dedicated deterministic regressions:
  - road-rage cross-source consolidation / Spokane detachment,
  - timeline contamination repair,
  - shark-policy vs shark-sighting separation,
  - broad-event quarantine / three-incident separation.
- Strengthened `test_production_registry_test_contract.py` so reintroducing a direct
  ROOT/data/editorial_story_registry.json dependency in pytest fails immediately.
- Live registry health remains protected outside pytest: Test Editorial Engine
  repairs and verifies a scratch copy; production repairs the real registry before
  generation.

## Safety

No generator logic, identity thresholds, article output, membership UI, Stripe,
Supabase, pricing, or reader-facing behavior changes in this patch.
