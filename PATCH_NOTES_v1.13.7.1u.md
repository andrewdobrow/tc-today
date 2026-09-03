# v1.13.7.1u — Unified Incident Identity Test Clock Alignment

## Scope
Test-only hotfix over v1.13.7.1t. No production/editorial code changes.

## Failure
`tests/test_unified_incident_identity_contract.py::test_editorial_engine_passes_source_evidence_into_registry`
used a fixed `default_published_at` of `2026-08-04T12:00:00Z`.

On September 3, 2026, that synthetic first story crossed the production 30-day lifecycle threshold and became `archived` before the second synthetic publisher rewrite was processed. The unified incident matcher intentionally skips archived stories, so the rewrite correctly became a new story under production lifecycle rules even though the test was intended to exercise cross-source incident identity rather than lifecycle aging.

This is the same class of calendar-driven test failure already repaired in v1.13.6.1c for `tests/test_editorial_engine.py`.

## Fix
The failing test now derives its synthetic publication time from current UTC at test-module execution, with microseconds stripped. Both synthetic articles remain within the active lifecycle window, so the test exercises the identity contract it was written to test.

Production lifecycle behavior is unchanged:
- 30-day archival threshold unchanged.
- archived stories remain excluded from unified incident matching.
- no resolver thresholds changed.
- no ALPR/custom-authority behavior changed.

## Validation against exact v1.13.7.1t checkout
- exact formerly failing test: 1 passed
- full Test Editorial Engine command: 1114 passed, 48 warnings
- package validation: 38 modules / 122 public exports
- 90 MiB repository guard: clean
- Python compile: passed
