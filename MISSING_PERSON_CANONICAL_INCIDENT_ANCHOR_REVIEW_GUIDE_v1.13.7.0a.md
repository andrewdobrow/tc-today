# v1.13.7.0a Review Guide — Missing-Person Canonical Incident Anchor Authority

## Production acceptance sequence

1. Apply this overlay over the current v1.13.7.0 shadow-ranking repository.
2. Run **Test Editorial Engine**.
3. Do not run Generate News unless tests are green.
4. Run **one** Generate News production workflow.
5. Inspect the Generate News log, canonical publication ledger, semantic publication report, archive, redirects, homepage, Martin County page, Crime & Safety page, Top Stories, and Latest News.

## Required Debevec outcome

Canonical permalink must remain:

`2026-08-29-martin-county-sheriffs-office-searches-for-missing-oklahoma-visitor-last-seen-at-chastain-beach`

The two known Aug. 30 escaped URLs must not remain independent live articles:

- `2026-08-30-martin-county-sheriffs-office-searches-for-missing-oklahoma-man-last-seen-at-hut`
- `2026-08-30-martin-county-sheriffs-office-searches-for-oklahoma-visitor-last-seen-at-hutchin`

They should consolidate/redirect to the Aug. 29 canonical.

## Expected identity evidence

The authoritative custom story should own:

`missing-person:michael-debevec`

The later publisher source should be bound to that canonical before any new-slug publication authority is granted.

Look for a log line beginning:

`AUTHORITATIVE CUSTOM INCIDENT ROUTE: binding feed source`

If the newer source contains material new facts, the existing Aug. 29 article may be updated in place. If it does not, the source should be suppressed. A new Debevec permalink is a release-blocking failure.

## Release blockers

Stop and inspect before further development if any of these occur:

- any third live Debevec permalink is created;
- either known Aug. 30 duplicate remains independently indexable/live;
- the later publisher source is classified as a separate canonical incident;
- material new reporting is published at a new URL instead of updating the custom canonical;
- a different named missing person is merged into the Debevec incident;
- Test Editorial Engine is red.

## Homepage ranking status

v1.13.7.0 homepage ranking remains recommendation-only. Do not promote ranking authority until this canonical-integrity hotfix is production-validated.
