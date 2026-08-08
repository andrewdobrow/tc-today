# Treasure Coast Today v1.13.2.1 — Emergency Publication Reliability Hotfix

Date: 2026-08-07
Baseline: cumulative v1.13.2.0 / v1.13.1.8-compatible overlay

## Why this release exists

The Aug. 7 production workflow successfully completed generation, archive reconciliation,
identity validation, permalink validation, and final canonicalization, then aborted on the
last county-membership authority check with exactly one unsupported live placement.

The root cause was a provenance handoff bug introduced by the new county authority model:
legacy archive rows that lack original source provenance can be conservatively preserved by
an explicit migration-only `county_membership_authority` marker, but `archived_story()` did
not copy that marker when projecting the archive row back onto a live category surface.
Later canonical rebinding could likewise adopt canonical copy/permalink without adopting the
canonical owner's persisted provenance. A valid recovered county story could therefore pass
archive authority and then fail live authority minutes later.

## Production fixes

1. Archive-to-live county provenance preservation
   - `archived_story()` now carries the persisted `county_membership_authority` marker.
   - Generated TCT copy still cannot create or self-authorize county membership.

2. Canonical-rebind provenance preservation
   - Final canonical rebinding now carries persisted canonical source fields,
     `event_identity`, and `county_membership_authority` together with canonical copy/URL.
   - Authority comes only from persisted canonical provenance, never generated copy.

3. Placement-level final county repair
   - After the final canonicalization boundary, county authority is enforced again.
   - Unsupported county metadata is stripped.
   - Unsupported county cards/heroes are quarantined locally.
   - If a county hero is removed, deterministic authority-checked archive recovery runs.
   - Canonicalization and county enforcement run once more before the existing hard validator.
   - This keeps the final gate fail-closed for content while preventing one repairable
     placement from discarding an otherwise successful full-site generation run.

4. Cumulative v1.13.2.0 protections retained
   - source-authoritative county membership
   - safe legacy archive migration
   - enforced Business & Development eligibility
   - fragmented unified-incident candidates remain advisory/no-write rather than fatal
   - all previous identity, custom-authority, permalink, freshness, and publication gates remain

5. Current manual article included
   - `custom_articles.json` contains the Aug. 7 FDOT Treasure Coast traffic report.
   - Image: https://treasurecoast.today/images/fdot.png

## What this release does NOT do

The production log also showed a broad burst of Google News RSS 503 responses/timeouts.
Those reduced feed coverage but did not terminate this run. This emergency release does not
redesign feed acquisition; that should be handled as a separate bounded increment after
production publishing is stable.

## Validation

- GitHub workflow-equivalent pytest boundary: 780 passed, 0 failed
- County/canonical/identity/category targeted suite: 58 passed, 0 failed
- Custom publication suite: 45 passed, 0 failed
- `scripts/validate_package.py`: passed (34 modules / 119 public exports)
- `apply_generator_runtime_hotfix.py`: idempotent; generator unchanged
- `apply_false_jurisdiction_hotfix.py`: verified; generator unchanged
- Exact archive-recovery provenance regression added
- Exact canonical-rebind provenance regression added

No generated HTML, archive.json, story registry, caches, feeds, or sitemaps are included.
