# TCT v1.13.7.1d — Late Material-Update Placement Suppression Authority

## Production failure

On Sep. 1, 2026, the Martin County run ingested and generated a major follow-up in the Michael Anthony Debevec II missing-person story: a body had been recovered in mangroves near the House of Refuge and investigators believed it was Debevec pending positive identification.

The generated Martin County card was then deleted by `_suppress_published_skip_placements()` as `published_skip_placement_suppressed` because durable custom incident identity correctly resolved it to the Aug. 29 Debevec canonical.

That suppression point ran **before** the existing late material-update write barrier. The later safeguard therefore never saw the generated follow-up.

## Root cause

The pipeline had two destructive published-story suppression stages:

1. pre-generation source suppression — already protected by `_promote_published_skip_material_updates()`;
2. post-generation/cached-placement suppression — **not protected by material-update adjudication**.

A story whose canonical identity became authoritative only after generated-placement identity stamping could therefore be deleted before semantic materiality evaluation.

## Fix

`_suppress_published_skip_placements()` now accepts the active semantic cache/report and, before deleting a canonical-bound generated or cached placement, invokes `_late_published_skip_material_update_promotion()`.

- If the late gate validates a material update, the placement is replaced with the authorized canonical-refresh payload and remains in the category.
- If the late gate finds no material update, normal duplicate suppression continues.
- If the semantic cache/report are not supplied (for isolated shadow/test callers), legacy non-production behavior remains unchanged.

Both production call sites — cached category reuse and freshly generated category output — now provide the semantic cache/report.

This does **not** weaken story identity, duplicate thresholds, or materiality standards. It only guarantees that materiality is evaluated before a destructive suppression point.

## Regression coverage

Added tests proving:

- a generated same-story major update reaches late materiality and survives suppression when promoted;
- a generated same-story no-change item is still suppressed after late materiality rejects promotion.

Validation on the patched repo:

- focused identity/material-update suites: **107 passed**;
- full editorial workflow test command (matching production exclusions): **1066 passed**.
