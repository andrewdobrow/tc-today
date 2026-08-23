# v1.13.6.7d — Hometown Legacy Archive Cleanup

## Scope
This is a narrow cleanup increment on top of v1.13.6.7c. It does **not** reopen Hometown News ingestion and does **not** purge all historical Hometown coverage.

## Production failures addressed
Two confirmed stale Hometown republications from the Aug. 22 production window had already entered TCT before v1.13.6.7b retired the source:

1. `2026-08-22-martin-county-deputy-stops-600000-gold-bar-scam-targeting-senior`
   - confirmed duplicate of TCT's Aug. 13 canonical
   - now removed from the active archive and permanently redirected to:
     `2026-08-13-martin-county-deputies-save-senior-from-600000-gold-bar-scam`

2. `2026-08-22-indian-river-county-creates-attainable-housing-trust-to-support-development`
   - confirmed stale republication of an Aug. 2 government action
   - no earlier TCT canonical exists
   - now removed from active archive, sitemap, archive recovery, and live placement surfaces
   - its old article path becomes a `noindex,nofollow` handoff to `/indian_river.html`

## Implementation
- Adds `data/source-retirement-cleanup.json`, a slug-scoped cleanup policy.
- Archive recovery filters policy tombstones before selecting heroes/cards.
- Live category surfaces remove any tombstoned placement before front-page hero selection and again after permalink rebinding.
- Final archive writing applies tombstones after normal canonical cleanup:
  - duplicate tombstones become canonical redirects;
  - stale unique tombstones are removed from archive/discovery surfaces and get noindex handoff pages.
- Source-domain proof is required. If a configured slug's archive provenance is not Hometown News, cleanup fails safe and preserves the row.
- Historical Hometown records not explicitly listed in the policy are untouched.

## Validation
- Hometown/source-retirement focused tests: 9 passed.
- Hometown + published-story + assignment-editor focused tests: 41 passed.
- Workflow-equivalent suite:
  `python -m pytest tests -q --ignore=tests/test_canonical_identity.py --ignore=tests/test_matcher_contract.py`
  - 949 passed
  - 45 existing `datetime.utcnow()` deprecation warnings
- `python scripts/validate_package.py`: 38 modules / 119 exports PASS
- generator runtime hotfix check: PASS
- false-jurisdiction guard check: PASS
- `python -m py_compile scripts/generate.py`: PASS

## Real archive dry run
Against the 843-record production archive from `tc-today-main (13).zip`:
- 843 -> 841 active archive records
- exactly 2 configured stale records retired
- 1 canonical redirect created
- 0 source-domain mismatches
- unrelated historical Hometown records remained intact
