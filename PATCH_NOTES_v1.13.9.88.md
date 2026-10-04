# TCT v1.13.9.88 — redirect identity recovery and missing-person guard

Apply this delta overlay on top of v1.13.9.87 / the current production repository.

## What this fixes

- Repairs the previously missed third Garry's Towing alias (`2026-10-02-miami-woman-jailed-after-tow-yard-shooting-triggers-murray-middle-school-lockout`) and binds every known Oct. 2-3 framing of that incident to the established Oct. 2 canonical permalink.
- Restores two independently established article permalinks that contaminated historical identity decisions had turned into unrelated redirects:
  - the Aug. 8 Port St. Lucie 77-year-old pond-death article;
  - the Oct. 1 Robert La Polla missing-father article.
- Recovery is exact and fail-closed: the generator restores the newest committed substantive HTML plus its matching archive row from Git history. It does not invent a body, timestamp, story ID, or source metadata.
- Fixes the active missing-person matcher failure that could interpret Treasure Coast place names such as `Fort Pierce` as person aliases.
- Bumps unified incident evidence to v6 so persisted older evidence is rebuilt under the corrected person/place rules.
- Adds explicit male/female missing-subject conflict evidence, preventing a missing father/man story from being destructively merged with a missing woman/mother story when no real person identity is shared.
- Broadens the Garry's Towing safety audit so it discovers same-incident Oct. 2-3 aliases rather than trusting only a hard-coded alias list.
- Adds fail-closed redirect protection for the recovered standalone permalinks and for any current-run missing-person redirect with a clear subject-identity conflict.

## Expected next production run

If the two independently established standalone pages are still damaged at startup, Generate News should log:

`Protected standalone permalink recovery restored 2 independently established article(s)`

The final redirect audit should report no protected standalone redirect sources, no current-run missing-person subject violations, and a passing Garry's Towing integrity check.

## Validation

- New v1.13.9.88 regression suite: 8 passed, 0 failed.
- Redirect / identity focused suite: 121 passed, 0 failed.
- Production-equivalent suite (same two known local legacy root-engine exclusions): 1,504 passed, 0 failed.
- Package validation: 42 modules imported, 123 public exports verified.
