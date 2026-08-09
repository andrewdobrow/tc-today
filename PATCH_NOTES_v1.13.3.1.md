# TCT v1.13.3.1 — Registry Preflight Fixed-Point Convergence

## Production/test failure addressed

`Registry preflight failed: deterministic repair did not reach a fixed point in one pass. Remaining merges: {'story_002776': ('story_002777',)}`

## Root cause

The registry preflight claimed to normalize the deterministic repair pipeline to a fixed point, but it actually applied one top-level repair pass and then treated any legitimate deterministic merge visible on the verification pass as fatal.

A first authoritative merge can expose another component only after evidence has been combined or moved. That does not mean the second merge is fuzzy or unsafe; it means the whole deterministic pipeline needs another pass.

The old verification also deep-copied the full persistent registry before rerunning repair, which is expensive at the current registry size.

## Change

- Repeats the same deterministic `repair_registry_payload()` pipeline in place until a complete pass reports no authoritative changes.
- Does not grant any new write authority to fuzzy/candidate-only evidence.
- Keeps a hard fail-closed ceiling of 16 passes. If convergence is not reached, the workflow still stops.
- Removes the full-registry deepcopy verification path.
- Adds a permanent regression reproducing a second-pass merge using the exact escaped story IDs `story_002776` and `story_002777`.

## Validation

- Package validator passed: 34 modules / 119 public exports.
- Registry + membership targeted regression suite: 37 passed.
- Fixed-point preflight regression file: 4 passed.
- Preflight against the supplied production-sized registry completed cleanly in one pass when already normalized.
