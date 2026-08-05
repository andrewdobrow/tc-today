# v1.13.1 — Unified Incident Identity Contract

## Purpose

Prevent the same real-world incident from publishing under multiple TCT permalinks
when publishers change headline wording, while also preventing unrelated incidents
from attaching through generic facts, broad locations, or milestone language.

## Core identity improvements

- Adds a deterministic source-fact incident evidence layer before sparse-key and
  semantic resolution.
- Uses event family, full names, structured locations and agencies, high-signal
  actions, and distinctive source wording as explainable identity evidence.
- Removes location/agency words and generic event terms from the independent
  evidence score so a shared city or words such as `fire reported` cannot authorize
  an attachment.
- Treats missing or empty fact sets as no evidence, never as complete overlap.
- Supports general source-framing drift when location, event family, headline
  continuity, and distinctive facts all corroborate one another.
- Routes a verified same-incident match through the established event canonical,
  preventing a changed generated event key from producing a second article.
- Preserves legitimate crash closure/reopening follow-ups through a constrained
  location + event type + distinctive fact + headline continuity contract.
- Extracts arrest counts so a fourth arrest is material information rather than a
  no-change duplicate.

## Registry and publication repair

- Consolidates the known Martin County road-rage/PIT-maneuver fragments under
  `story_002076`.
- Redirects the August 5 duplicate road-rage permalink to the August 4 canonical
  article and removes the duplicate from archive/live placements during publication.
- Detaches the Spokane wildfire article from Geoffrey Lang coverage.
- Consolidates additional verified fragments discovered by the same general
  evidence contract to a fixed point.
- Makes the repair idempotent: a legitimately consolidated sparse-key incident is
  not quarantined on the next run.
- Adds fragmented unified incidents to the fail-closed identity-integrity and
  activation preflight reports.

## Canonical road-rage URL

`/articles/2026-08-04-fort-myers-man-arrested-after-road-rage-pit-maneuver-crashes-familys-suv-into-fe.html`
