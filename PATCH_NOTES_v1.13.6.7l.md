# v1.13.6.7l — Semantic Guard Authority Stabilization

This increment removes several contradictory late-stage authorities that were still able to corrupt otherwise-correct editorial packages.

## Production fixes

1. **Named policy/measure framing is clause-semantic rather than noun-matching.** A lead such as `Resolution 26-R70, raising the annual solid waste assessment ...` now defines the resolution even when the headline says `trash fee`. A bare procedural mention such as `Resolution 26-R70 passed Monday` still fails closed.
2. **Story-aware update context recognizes concrete animal-rescue continuity.** A later surrender/adoption development that explicitly recounts the earlier rescue/cruelty event is no longer rejected as `original_event_context_missing`.
3. **Enforced topic-category contracts are final topic authority.** Once the enforced Crime/Business/etc. contract proves a placement eligible, an older/stale classifier label cannot veto it. The enforced contract can still reject an actually off-topic item even if the classifier says otherwise.
4. **County pages may mirror a fresh topic hero.** Homepage semantic hero dedupe no longer demotes a county hero solely because a topic section uses the same story. Topic-vs-topic duplicate protection remains active.

## Assignment-editor final-pipeline alignment

5. **The shadow reuses live publication identity.** Per-run semantic publication outcomes are recorded by normalized source URL and consumed by the publication-isolated shadow.
6. **The shadow also reuses pre-generation canonical authority.** The canonical context slug attached by the live publication ledger is carried into the shadow packet. Two selected sources already bound to the same canonical collapse without another model call.
7. **Angle-shift recall is shadow-only and adjudication-only.** If authoritative identity is unavailable, selected same-locality/high-signal-event-family pairs with close timing and enough textual continuity are recalled for the same semantic publication adjudicator used by live production. Recall alone never merges stories. An unrelated same-city event family does not reach adjudication.
8. **Independent follow-ups remain separate.** A publication-authorized accountability/consequence follow-up is never collapsed merely because it relates to the same underlying event.
9. **Material updates replace the older shadow representation atomically.** A validated same-event material update is represented once, by the newer selected source.
10. **All publication-to-shadow bridge state is per-run only** and is cleared at build start.

## Natural regression fixtures

- Port St. Lucie `$14.83` / `Resolution 26-R70` trash-fee lead.
- Palm City 36 Border Collies surrender/adoption update.
- Fort Pierce BB-gun manslaughter Crime eligibility versus stale county-only classifier label.
- Vero Beach chase appearing legitimately on Crime and Indian River County.
- Port St. Lucie NWS-confirmed tornado versus resident-cleanup angle.
- Separate tornado alert/accountability follow-up remains independent.
- Unrelated Port St. Lucie garage fire is not considered a tornado-cluster candidate.

No source-specific tornado rule, trash-fee vocabulary mapping, or Border Collie story ID is used as publication authority.
