# TCT v1.13.9.67 — Weekend Roundup Dedup + Publication Clock Fix

## What this overlay fixes

1. Removes the Oct. 2 WPBF-derived weekend roundup from active TCT discovery and redirects its URL to TCT's own Oct. 3–4 curated events guide.
2. Cleans the prior Sept. 25 WPBF roundup and redirects it to TCT's Sept. 26–27 curated guide.
3. Rejects publisher-authored multi-event weekend roundups at feed ingestion, Things To Do eligibility, and final permalink publishability. TCT custom/manual weekend guides remain explicitly exempt.
4. Fixes brand-new permalink publication time so a new TCT article always receives the current TCT publication timestamp rather than inheriting an older persistent-story timestamp.
5. Adds an additive editor-retirement overlay file instead of replacing the existing source-retirement policy file.

## Expected first production run

- `2026-10-02-greenmarket-bahamian-festival-and-oktoberfest-headline-treasure-coast-weekend.html` is removed from archive/live discovery and becomes a canonical redirect to `2026-10-02-treasure-coast-weekend-events-oct-3-4.html`.
- `2026-09-25-bacon-and-bbq-festival-at-midflorida-event-center-tops-weekend-events.html` is removed from archive/live discovery and becomes a canonical redirect to `2026-09-22-treasure-coast-weekend-events-sep-26-27.html`.
- Future external generic weekend-event roundups such as “Fun things to do … this weekend” are discarded before article enrichment/model generation when identifiable from the feed headline.
- Defense-in-depth blocks also prevent such a roundup from becoming a permalink if it reaches a later stage.

## Scope

This is a delta overlay. It does not replace the existing `data/source-retirement-cleanup.json`; the new `data/source-retirement-editor-overrides.json` is merged additively.

## Validation

- `python -m py_compile scripts/generate.py`: PASS
- 122 targeted regression tests: PASS
