# TCT v1.13.9.25 — Missing-person location punctuation

## Problem
FDLE result rows currently provide locality values such as `Vero Beach,FL` and `Port Salerno,FL`. TCT rendered those raw values directly, so the Missing Persons directory cards and individual profile pages displayed the city/state without the normal space after the comma.

## Fix
- Added one display-only locality normalizer in `scripts/update_missing_persons.py`.
- Public output now renders `City, FL` consistently on directory cards, profile intro text, case-detail facts, meta descriptions, Open Graph descriptions, and structured-data descriptions.
- Source values in `data/missing-persons.json` are intentionally left untouched; this is presentation formatting only.
- Existing records, FDLE IDs, county membership, profile URLs, images, and completeness logic are unchanged.

## Validation
- Rendering regression proves a raw `Port Salerno,FL` source value is displayed as `Port Salerno, FL` everywhere public-facing and that the unspaced form does not leak into the generated directory/profile HTML.
- `tests/test_missing_persons.py` + `tests/test_missing_person_identity_continuity.py`: 42 passed.
- Local render-only validation completed with all 10 current profiles and no validation failures.

## Deployment
Apply this delta, run **Test Editorial Engine**, then run the **Update Missing Persons** workflow so the live directory and all individual profiles are regenerated from current FDLE data with corrected punctuation.
