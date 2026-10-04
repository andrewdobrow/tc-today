# TCT v1.13.9.86 — Canonical permalink identity emergency fix

Apply on top of v1.13.9.85.

## Incident confirmed

The Garry's Towing shooting/chase was incorrectly merged with the unrelated Aug. 4 Martin County road-rage story by the destructive unified-incident redirect path.

The repository's canonical cleanup history contains the exact bad decision:

- source: `2026-10-02-shooting-at-stuart-tow-yard-prompts-murray-middle-lockout-chase-with-pit-maneuve`
- wrong target: `2026-08-04-fort-myers-man-arrested-after-road-rage-pit-maneuver-crashes-familys-suv-into-fe`
- stage: `unified-incident-identity`
- confidence: 96%
- shared people: none
- shared locations: none
- shared agencies: none
- shared concepts: `martin_stuart`, `pit_maneuver`
- title overlap: 0.18

The failure was deterministic, not an LLM semantic-gate decision. A bare law-enforcement PIT maneuver was being treated as evidence that the underlying incident was `road_rage`. The road-rage matcher then accepted the generic combination of a PIT maneuver plus Martin/Stuart context as sufficient identity.

The Oct. 3 workflow also shows the new tow-yard follow-up was generated as a fresh placement before the later Canonical Story Manager cleanup. The semantic publication gate reported zero candidate pairs, so the destructive redirect happened in the downstream canonical cleanup path.

## Fixes

1. **PIT no longer means road rage**
   - `tct_engine/unified_incident_identity.py` no longer classifies a story as road rage merely because police/deputies used a PIT or police maneuver.
   - `tct_engine/timeline_coherence.py` uses the same corrected event-family rule.
   - Road-rage identity remains available for explicit road-rage wording or a civilian vehicle forcing/chasing another vehicle off the road.

2. **Headline-first incident family**
   - Unified incident evidence now prefers the family expressed by the current article headline before falling back to pooled body/history text.
   - This prevents facts accumulated on a persistent story record from contaminating the family assigned to a later article.

3. **Removed the destructive six-word fallback**
   - `_same_event_items()` no longer permits destructive identity from generic shared-token counts alone.
   - It now requires the existing cross-source same-event evidence contract, including locality, event-family compatibility and concrete corroborating facts.

4. **Durable Garry's Towing incident anchor**
   - Oct. 2 and Oct. 3 framings of the Garry's Towing shooting/chase resolve to one deterministic event key when the tow-yard, Martin/Stuart, incident and named/landmark anchors agree.

5. **Permanent permalink ownership**
   - Canonical URL:
     `2026-10-02-two-miami-women-charged-after-tow-yard-shooting-near-stuart-sparks-school-lockou`
   - Audited aliases:
     - `2026-10-02-shooting-at-stuart-tow-yard-prompts-murray-middle-lockout-chase-with-pit-maneuve`
     - `2026-10-03-two-miami-women-charged-after-gunfire-chase-at-martin-county-tow-yard`
   - The canonical URL can never be emitted as a redirect source.
   - Either alias can only redirect to the Oct. 2 canonical.
   - A current-run attempt to point any of these URLs at another story fails the production run before destructive output is written.

6. **Self-healing production recovery**
   - Before generation, the emergency repair detects the corrupted permalink state.
   - It prefers the newest surviving substantive alias body when one exists, but rebinds it to the Oct. 2 canonical URL.
   - If the substantive Oct. 2 page was already replaced by a redirect, it can recover the last substantive committed page/archive row from git history. The production checkout already uses `fetch-depth: 0`.
   - Historical publication time is recovered from committed metadata. The repair refuses to invent a timestamp if history is unavailable.
   - Once the canonical and all aliases are healthy, the repair becomes idempotent and does nothing on later hourly runs.

7. **Cumulative redirect safety audit**
   - Every run writes `data/canonical-redirect-safety-audit.json`.
   - It reports redirect chains, cycles, missing targets, >45-day date-gap advisories and headline event-family conflicts.
   - Current-run redirect chains or missing targets fail closed.
   - Historical advisories are reported rather than automatically deleted, avoiding destructive guesses about legitimate long-running stories.

## Forensic scope check on the supplied repository snapshot

The existing cumulative redirect ledger contained 210 redirects. A deterministic review found:

- 0 missing targets
- 4 redirect chains
- 2 redirects with a source/target date gap over 45 days
- the Garry's Towing -> Aug. 4 road-rage mapping is the only one that is plainly contradictory from its own stored identity trace

The other long-gap mapping is a Fort Pierce homicide follow-up and is not automatically rewritten by this patch. The new audit report will expose the full post-v1.13.9.86 production ledger for review after the first run.

## Validation

Focused permalink/identity/canonical regression suite:

- 67 passed
- 0 failed

Production-equivalent suite:

- 1,484 passed
- 0 failed

Package validation:

- 42 modules imported
- 123 public exports verified

Existing `datetime.utcnow()` deprecation warnings are unchanged.

## Scope

No dynamic production data files are included in this overlay. In particular, it does not overwrite `archive.json`, `data/canonical-redirects.json`, editorial registries, RSS, generated article HTML, or Bunny image state. The next normal Generate News run repairs production state from the checked-out repository/history and then applies the hardened contracts.
