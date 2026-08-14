# Follow-up Evidence Precision Review Guide — v1.13.6.1

Review `data/editorial_observability.json` → `follow_up_detection.retrospective` after each production run.

Expected invariants:

1. `candidate_scope` is `distinct_article_transitions`.
2. Exact normalized source-article URL transitions appear under `same_source_evolution_examples`, not `examples`.
3. `same_source_evolution_count` is nonzero when publishers update an existing article in place.
4. `event_family_conflict` may block activation only when both event families are known and materially different; `unknown-event-*` is not a conflicting family.
5. Headlines that already say `deadly`, `fatal`, `suspected suicide`, etc. already contain death evidence; a later `dies/death` wording change alone is not a novel milestone.
6. `publication_behavior_changed` remains false and `enforcement_ready` remains false.
7. Manually review every `activation_eligible` distinct-article candidate before any future enforcement release.
