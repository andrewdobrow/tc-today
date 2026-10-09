# TCT v1.13.9.107 — Authoritative Custom Scoop Continuity Repair

## Incident
On 2026-10-09 TCT generated a second article for the Port St. Lucie Westmoreland assisted-living/petroleum-contamination dispute even though TCT had already published an authoritative manual scoop on 2026-09-29.

Canonical:
`2026-09-29-residents-seek-halt-port-st-lucie-assisted-living-project-petroleum-cleanup-site`

Escaped duplicate:
`2026-10-09-port-st-lucie-residents-question-contamination-near-approved-assisted-living-sit`

## Root cause
The Sept. 29 custom article was correctly marked `is_custom`, `authoritative_custom`, and had a durable custom publication identity, but its immutable event snapshot had no incident family, agency, named person, street anchor, or known-event key. The existing generic near-term custom-subject lock only covered three calendar days.

In addition, `_find_authoritative_custom_incident_match()` projected the incoming source through `_event_audit_item()` before durable custom matching. That audit projection intentionally omits fetched publisher article text, discarding the strongest factual evidence before custom-authority comparison.

## Repair
- Durable custom matching now receives the original rich source/custom records before audit projection.
- Added a conservative 4–45 day extended custom-subject identity contract for manual authoritative TCT stories.
- Extended matching requires shared jurisdiction, no structured identity conflicts, at least four shared headline concepts, at least ten shared distinctive facts, at least four supporting facts beyond headline concepts, and >=80 deterministic story-match confidence.
- The contract uses final published custom-article facts only as corroboration and does not rewrite immutable source identity.
- Added a permanent exact redirect from the Oct. 9 duplicate to the Sept. 29 canonical.
- Category memberships from the duplicate are merged onto the canonical before the duplicate is removed.

## Safety
The extended contract fails closed on a different Port St. Lucie assisted-living development and expires after 45 days. Existing cross-source/custom/canonical authority tests remain green.

## Validation
- 114/114 relevant identity/canonical/dedup tests passed.
- `python -m py_compile scripts/generate.py` passed.
