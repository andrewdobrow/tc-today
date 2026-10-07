# TCT v1.13.9.96 — Custom polling-place duplicate hard stop and Oct. 7 repair

Apply on top of v1.13.9.95.

## Incident
TCT had already published the authoritative custom article:

`2026-10-05-st-lucie-county-changes-polling-location-for-precincts-39-and-52-for-nov-3-election`

A later CBS12 rewrite of the same St. Lucie County Precincts 39/52 polling-place notice escaped custom-authority deduplication and created a second public URL:

`2026-10-07-st-lucie-precincts-39-52-move-to-lakewood-park-church-for-nov-3-vote`

The existing near-term custom-subject guard required shared ordered headline subject phrases. The two headlines described the same event but used sufficiently different wording that they did not satisfy that headline-phrase contract. The general cross-source evidence correctly treated them as related but did not grant destructive identity authority, so the generated copy survived.

## Prevention
- Adds a deterministic polling-place-change identity for local election notices.
- Identity requires all of:
  - polling-place/location change context;
  - election/voter/ballot context;
  - a recognized Treasure Coast county;
  - an exact precinct-number set; and
  - the specific election date.
- For this incident both articles resolve to:

`polling-place-change|st-lucie|2026-11-03|precincts-39-52`

- The identity is wired into authoritative custom deduplication and custom event-key persistence.
- A publisher rewrite for the same precincts/election is routed to the existing custom authority instead of minting a parallel permalink.
- Different precincts or a different election date do not match.
- No global similarity threshold is lowered and no generic redirect rule is broadened.

## Repair
- Permanently binds the already-public Oct. 7 duplicate slug to the Oct. 5 custom canonical.
- On the next generation run, canonical cleanup removes the duplicate archive record/discovery placement and writes the Oct. 7 URL as a redirect to the Oct. 5 article.
- The explicit slug migration remains as a permanent regression repair even if historical duplicate metadata later becomes sparse.

## Files
- `scripts/generate.py`
- `tests/test_authoritative_custom_incident_lock.py`

The test-file change is intentional in this patch because this is production identity/deduplication logic, not a content-only update. It permanently reproduces the escaped Oct. 7 URL and guards both prevention and repair behavior.

## Validation
- Polling/custom-authority targeted suite: 17/17 passed.
- Broader applicable custom/canonical/identity/redirect suite: 222/222 passed.
- Six tests in `tests/test_canonical_identity.py` were not runnable from the uploaded repo because its session fixture expects a root `engine.py` that is not present in the uploaded package; those tests fail at fixture setup before loading the changed generator.
- `scripts/generate.py` compile check passed.
