# TCT v1.13.3.4 — Autonomous Timeline Containment

This patch closes the remaining production-state failure path that allowed a
single repairable persistent-story timeline violation to abort an otherwise
successful scheduled build.

## Root cause

The failing story was not a one-off bad ID. Publisher page body/sidebar text could
supply unrelated death language and entities to incident identity, creating
`named-person-death:*` authority for articles whose actual titles were about a
different event. A previously contaminated story could then accept incompatible
fresh evidence during the run. The load-time registry repair had already passed,
but the final validator discovered the new timeline conflict and hard-failed.

## Changes

- Named-person-death identity is now title-gated. Body/entity evidence may resolve
  the person's name only after title-level evidence establishes that the article is
  actually a death/mourning story.
- Unsupported legacy `named-person-death:*` event authority is deterministically
  revoked when a story has no title-level death evidence.
- Timeline coherence now recognizes animal-cruelty incidents as a distinct family,
  preventing dog-abuse coverage from being treated as compatible with unrelated
  fire/business events.
- Current-run registry containment now:
  - revokes unsupported structured event keys,
  - removes stale broad event-index mappings,
  - splits high-confidence incompatible timeline components immediately,
  - quarantines only residual contamination that cannot be repaired safely,
  - rebuilds active event/incident indexes,
  - revokes stale current-run decision authority for every affected story.
- The final persistent-identity validator now gets one bounded deterministic
  self-heal pass for expected current-run drift. After a split/quarantine, archive
  rows are rebound only through exact source identity; otherwise the stale story ID
  is revoked.
- The final validator still fails closed for unresolved/systemic authority
  corruption, circular story-ID authorization, containment errors, or any
  violation that remains after bounded repair.
- Full registry repair now treats index-only cleanup as a persisted change and
  rebuilds incident-anchor ownership from the final post-split/post-merge graph.

## Regression coverage

Synthetic regressions cover:

- unrelated body/sidebar death text attempting to create death identity,
- animal-cruelty + unrelated fire contamination,
- final-gate deterministic timeline self-heal and exact-source archive rebinding,
- stale broad event-index cleanup and fixed-point behavior,
- current-run broad mapping containment.

The tests remain independent of mutable production story IDs and do not read the
live production registry as a regression fixture.

## Validation

- Workflow-equivalent pytest suite validated in two isolated batches: 403 passed +
  398 passed = 801 passed.
- Package validation: 34 modules imported and 119 public exports verified.
- Python compile validation passed for every changed Python module/test.
- The exact contaminated-state shape was replayed locally: when the unrelated fire
  entry is attached, bounded containment splits the timelines, removes the bogus
  death authority, leaves both stories active and coherent, and produces zero
  residual timeline violations.

## Safety / scope

There is no story-ID-specific exception for the observed failure. No paywall,
Subscribe UI, Stripe pricing, Supabase configuration, article generation prompt,
or reader-facing membership behavior is changed by this patch. Membership remains
dark while production stability is verified.
