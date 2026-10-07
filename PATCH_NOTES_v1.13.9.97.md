# TCT v1.13.9.97 — Exact Oct. 7 polling duplicate redirect only

Supersedes v1.13.9.96. Apply on top of v1.13.9.95, or apply over v1.13.9.96 to roll back the broader polling-place identity changes.

## Scope
This patch intentionally treats the Oct. 7 St. Lucie polling-place duplicate as a one-off repair. It does **not** change TCT's general deduplication matcher, thresholds, incident identity, custom-authority logic, or event-key generation.

## Exact repair
The already-public duplicate URL:

`2026-10-07-st-lucie-precincts-39-52-move-to-lakewood-park-church-for-nov-3-vote`

is permanently retired to the existing custom canonical:

`2026-10-05-st-lucie-county-changes-polling-location-for-precincts-39-and-52-for-nov-3-election`

On the next generation run, canonical cleanup:
- removes the Oct. 7 duplicate slug from the cleaned archive used for live discovery surfaces;
- writes the Oct. 7 article path as a canonical redirect page;
- writes a 301 rule from the Oct. 7 URL to the Oct. 5 custom article; and
- preserves the Oct. 5 custom article as the live canonical.

## v1.13.9.96 rollback
The generalized `_polling_place_change_identity` function and its integration into durable custom matching/event identity are absent. The pre-.96 `tests/test_authoritative_custom_incident_lock.py` is included only to restore that file if .96 was already applied; no new test contract is being added in .97.

## Files
- `scripts/generate.py`
- `tests/test_authoritative_custom_incident_lock.py` (pre-.96 restore only)

## Validation
- Existing authoritative custom incident suite: 12/12 passed.
- Broader applicable canonical/redirect regression set: 43/43 passed.
- One-off Oct. 7 redirect verification: 1/1 passed.
- `scripts/generate.py` compile check passed.
- Confirmed `_polling_place_change_identity` is absent.
