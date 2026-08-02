# TCT v1.13.0.1 — Semantic Material Update Transaction Integrity

## Purpose

The first live v1.13.0 material-update run successfully composed and published the Martin County shark-fishing update, but the same incoming source was evaluated a second time later in forward publication. That redundant pass correctly failed novelty validation and produced a misleading update hold. Separately, registry consolidation merged the incoming fragment into the canonical persistent story without first verifying that the combined registry record remained coherent. The merged record then failed the persistent story identity integrity gate as `active_contaminated_story=story_001155`.

This hotfix makes material-update publication and registry consolidation transactional and fail-closed.

## Changes

- Material-update registry directives are now created only for updates that reached a completed `material_updates[]` publication record. A Claude identity decision that was held during composition can no longer merge persistent story records.
- Every semantic registry merge is preflighted on a deep copy. If the merged record would trigger any persistent-story quarantine reason, the merge and alias are skipped and retained as a pending directive instead of contaminating the active canonical story.
- Retroactive canonical article updates are staged on a copy and written atomically. The archive row is committed only after the rendered article page is successfully replaced.
- A verified source already absorbed into a canonical material update is recognized before the forward semantic gate. The live placement is rebound to the canonical page without a second composer call or false update hold.
- Semantic diagnostics now count `material_update_replays_suppressed` and report `merge_would_contaminate_target` when registry consolidation is safely deferred.

## Expected shark-fishing result

The July 29 canonical article remains the only active public page, the August 1 URL remains redirected, and the same WPTV source is not recomposed during forward publication. If the fragmented registry record cannot be merged without violating story coherence, the public update still succeeds while the registry merge is held for a later targeted repair. The production run must not fail the persistent story identity integrity contract.
