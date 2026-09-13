# Treasure Coast Today v1.13.9.20

## Purpose

This delta is the follow-up to the Ronald Corbin permalink incident and the failed v1.13.9.19 production workflow. It repairs confirmed historical redirect corruption, hardens destructive permalink consolidation, fixes the material-update invariant that stopped the .19 workflow, and improves Event structured data without inventing metadata.

## Redirect audit and repair

- Audited the v1.13.9.19 cumulative redirect manifest: 220 permanent redirects.
- Confirmed 29 erroneous redirects using historical repository snapshots, surviving article/source lineage, and event identity evidence.
- Restored 16 independent article permalinks as substantive self-canonical pages.
- Retargeted 13 genuine duplicate aliases to the verified correct canonical article.
- Preserved 2 suspicious-looking redirects after historical review showed they were intentional same-story migrations.
- Final manifest: 204 permanent redirects.
- Full decision log: `REDIRECT_AUDIT_2026-09-13.md`.

## Permalink safety hardening

- A persistent story ID by itself can no longer authorize destructive consolidation of two published URLs.
- A stored/transitive incident anchor by itself can no longer authorize a redirect.
- A structured incident can still authorize a true duplicate only when the same write-authoritative anchor is independently recomputed from both published records.
- Historical known-event, canonical-ledger, structured-incident, and unified-incident paths now require direct pairwise evidence before sacrificing a permalink.
- The 16 restored permalinks are fail-closed anchors: a new current-run redirect attempt stops production before `_redirects` is written.
- The 13 repaired aliases are target-locked to their audited canonical destinations.
- Stale historical bad rows are repaired rather than being allowed to overwrite restored articles again.

## v1.13.9.19 workflow failure

The .19 workflow reached redirect processing but failed at the terminal material-update publication invariant after the Port St. Lucie 9/11 remembrance update was intentionally rejected by a later context-quality gate.

v1.13.9.20 adds an exact source-URL-bound final waiver. An explicitly held or already-absorbed source no longer produces a false missing-update failure, while a different selected update for the same canonical article still fails closed if it disappears.

## Google Event structured data

- `events.html` now emits an `ItemList` of event URLs rather than nested `Event` objects on the calendar listing.
- Individual event detail pages remain the canonical `Event` schema surfaces.
- Source parsers retain truthful organizer, performer, offer, and event-image metadata when supplied.
- Event detail pages emit `organizer`, `performer`, `offers`, and `image` only when the underlying event data supports them.
- Free events may emit a $0 Offer; descriptive/ambiguous price prose is not converted into a fake numeric offer.
- Generic TCT/category imagery is not misrepresented as an event image.

## Validation

- Focused redirect / event / material-update / canonical-identity regression suite: 186 passed, 0 failed.
- Broader suite, excluding two pre-existing test modules that require the absent root-level `engine.py`: 1,327 passed, 0 failed.
- The excluded legacy modules account for 7 pre-existing setup errors and are unrelated to this delta.
- Static redirect verification: 204 manifest rows match 204 `_redirects` rules; none of the 16 restored standalone slugs remain redirect sources; all 13 repaired aliases point to their audited targets; redirect sources are absent from `archive.json`.

## Deployment

Apply this delta on top of the v1.13.9.19 repository commit. Then run **Test Editorial Engine** followed by **Update Treasure Coast Today / Production**. The previous .19 production workflow failed, so do not treat its generated output as a completed deployment.
