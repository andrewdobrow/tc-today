# TCT v1.11.7.4 — Live Publication Receipt Reconciliation

## Incident

The v1.11.7.3 production run completed category generation and archive writing, but the final forward-live-identity contract stopped deployment with four `archive_entry_missing` violations.

Two article families were involved:

- Fort Pierce Wells Fargo ATM armed-robbery headline variants.
- Indian River County Fire Rescue / Geoffrey Lang death headline variants.

`write_archives()` correctly skipped one thin copy and one cross-category duplicate, but those skipped objects remained on live category surfaces. Their internal TCT links therefore had no active archive owner when the final identity gate ran.

## Repair

- Marks intentionally skipped publication objects with a deterministic skip reason.
- Adds a post-publication receipt reconciliation pass before the final identity gate.
- Rebinds strong same-run headline variants to the canonical archive page that was actually written.
- Permits exact external-source recovery even when a fragmented story ID is present.
- Adds a narrow local first-responder death identity bridge for the exact Fire Rescue / firefighter / death wording variation.
- Removes unresolved non-custom cards and heroes that were intentionally not published.
- Restores removed category positions only from verified permanent archive pages.
- Leaves unresolved custom and weather publications fail-closed for the existing final contract.
- Writes `data/live-publication-reconciliation.json` with rebound, removal and protected-unresolved evidence.

## Safety boundary

This patch does not weaken the forward identity contract and does not create fuzzy archive URLs. Same-run headline recovery requires an existing safe archive row, an existing article file, current-run date evidence and strong event identity. Any unresolved protected publication still stops deployment.

## Validation

- Exact production-pair regression: passed.
- Focused permalink/publication tests: 16 passed.
- Workflow-equivalent suite: 360 passed.
- Package validation: 29 modules and 98 public exports.
- Existing warnings: 17 `datetime.utcnow()` deprecation warnings.
- GitHub Actions and production have not yet run with v1.11.7.4.
