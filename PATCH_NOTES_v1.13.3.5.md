# TCT v1.13.3.5 — Cross-Source Reprint Lock

This patch closes a pre-publication identity hole that allowed a later publisher's
version of an already-covered local incident to mint a second TCT permalink days
after the original story.

## Root cause

The feed/fetch pipeline already carried the full fetched publisher article in
`article_text`, but `_event_identity_snapshot()` selected source text with an `or`
chain in this order: `source_summary`, `summary`, `teaser`, then `article_text`.

That meant any ordinary RSS summary silently discarded the full publisher article
from the authoritative cross-source identity snapshot. Source quality could report
`full`, and article generation could see the full source, while the duplicate
barrier saw only a thin teaser. Names, exact streets/intersections, police agencies,
vehicle details and other hard event anchors were therefore absent from the
identity decision. A delayed second publisher could be classified as only a
possible relationship and still mint a new URL.

The reported Port St. Lucie road-rage pair reproduces this failure shape: the
original Aug. 6 canonical contains strong incident anchors, while a thin later RSS
summary is not independently sufficient to authorize canonical reuse.

## Changes

- Full fetched publisher text is now the primary immutable identity evidence.
  `article_text`, source summary, summary and teaser are combined and deduplicated
  instead of allowing the shortest field to hide the richest one.
- Generated TCT body copy is still excluded from immutable source identity. This
  preserves the authority boundary and prevents model-written background prose from
  redefining an event.
- Known-event classification gets a larger bounded slice of source-facing text so
  the same fetched evidence is available to deterministic identity extraction.
- A deterministic **late cross-source reprint lock** now runs at three layers:
  1. normal source identity before generation,
  2. final-copy barrier immediately before a new permalink can be created,
  3. bounded retrospective archive repair for already-minted recent duplicates.
- The late-reprint repair is not fuzzy headline authority. It requires:
  - publication gap of no more than 7 days,
  - the same local jurisdiction,
  - the same event family,
  - strong topic/headline continuity,
  - substantial distinctive-fact overlap, and
  - independent incident anchors: participant + incident corroboration, or at
    least two shared street-level anchors + the same agency.
- Generic same-city crashes/crime stories cannot merge merely because their wording
  looks similar.
- Retrospective repair scans a bounded rolling horizon and caches final-copy feature
  extraction so it remains suitable for every scheduled production build.
- When an already-published delayed reprint is proven, the earlier canonical URL is
  retained and the later URL becomes a redirect. It is not deleted or 404'd.
- New diagnostics are written to:
  - `data/late-reprint-identity-lock-pre_publication.json`
  - `data/late-reprint-identity-lock-same_run_final_barrier.json`

## Regression coverage

A new synthetic regression reproduces the reported escape class without using live
story IDs or the mutable production registry:

- a full publisher article exists,
- a thin RSS summary is also present,
- the two publishers use rewritten road-rage headlines three days apart,
- the incoming item has a fragmented/new story ID,
- the full source contains the same participant, streets, police agency and crash
  facts.

The regression proves that the source binds to the existing canonical before
publication and that an already-minted later copy is removed from the archive and
redirected to the earlier permalink. A separate same-city unrelated-crash test
proves the new late-reprint lock does not merge a different incident.

## Validation

- Workflow-equivalent editorial suite: **806 passed**.
- Focused cross-source / authority suite: **38 passed**.
- Package validation: **34 modules imported / 119 public exports verified**.
- Generator runtime-hotfix and false-jurisdiction baked-in checks passed.
- Current production archive audit: **350 recent records scanned, 0 false-positive
  redirects** before injecting the regression duplicate.
- With a synthetic copy of the reported Aug. 9 road-rage reprint added to the
  current archive, the repair redirected exactly **1** URL to the existing Aug. 6
  canonical and produced no additional redirects.

## Safety / scope

There is no exception for a numeric story ID, publisher, or the reported slug.
The fix applies to the failure class. Membership/paywall UI remains unchanged and
reader-facing membership is still dark.
