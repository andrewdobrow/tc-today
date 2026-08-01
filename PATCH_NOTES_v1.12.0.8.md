# v1.12.0.8 — Persistent Story Identity Integrity

## Purpose

This release removes circular trust between the persistent story registry and canonical publication writes. A story ID is now a candidate-retrieval hint until the incoming source independently agrees with the canonical event.

## Root-cause fixes

- City-level `traffic-crash-*` and `fire-*` keys are classified as event classes, not incident identities.
- New crash and fire events receive stable article-specific suffixes.
- Broad event keys cannot populate or retain `event_to_story` ownership.
- Multi-incident broad-key stories are quarantined during registry repair.
- Quarantined story IDs are removed from archive rows before publication reconciliation.
- Persistent story IDs cannot authorize a canonical write without exact source identity or hard source-derived event proof.
- Exact normalized source URLs remain independently authoritative.
- Source-facing summaries take precedence over generated article prose when immutable event identity is first stored.
- Generic pseudo-locations such as `florida-highway` no longer count as precise incident locations.
- The production gate writes `data/persistent-story-identity-integrity.json` and fails closed on broad mappings, active contaminated stories, quarantined archive references, or circular story-ID authorization.

## One-time data repair

- Quarantined polluted `story_000011`.
- Restored the Port St. Lucie liquor-store DUI article to its established July 29 permalink.
- Restored the Marie Martin fatal intersection crash to its separate July 31 permalink and existing `story_001557` identity.
- Assigned the Urban Air/Emma Riddle wrongful-death page to its independent story.
- Removed the invalid fatal-crash-to-liquor-store redirect.
- Revoked an unrelated quarantined firefighter story ID from its archive article without removing the article.

## Validation target

- `python scripts/validate_package.py`
- `python -m pytest tests -v --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`
- `data/persistent-story-identity-integrity.json` must report `passed: true` and `violation_count: 0`.
