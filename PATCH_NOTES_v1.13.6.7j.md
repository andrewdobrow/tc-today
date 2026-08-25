# Treasure Coast Today v1.13.6.7j — Terminal Material-Update Recall / Canonical Freshness Integrity

## Purpose
Close the last deterministic contamination found after v1.13.6.7i: a source could be proven to belong to an already-published canonical only at the terminal publication barrier and then be suppressed without ever receiving a material-update decision. In the Aug. 24 Port St. Lucie tornado case, that allowed the fresh NWS confirmation/damage findings to collapse back to the older pre-survey canonical article.

## Production changes

### 1. Terminal published-story skip now recalls materiality
When `_published_skip_canonical()` resolves a proven same-story canonical at the final write barrier, a genuinely newer full source now receives one final bounded semantic materiality decision before suppression.

The path is target-bound and cannot mint a new permalink:
- identity is already proven;
- the semantic decision may only preserve the exact canonical or authorize `update_existing` for that exact canonical;
- a contradictory `new_story` answer fails closed;
- validated material updates are grounded through the existing semantic material-update composer;
- destructive write authorization is stamped before and after composition;
- only a fully validated composition proceeds to the normal canonical update path.

No-update, ambiguous, shallow, non-newer, already-absorbed, or failed-composition sources remain suppressed and preserve the existing canonical page.

### 2. Fail-closed working-copy transaction
The late materiality path operates on a deep copy until composition and write authorization succeed. A failed update attempt cannot leak `update_existing`, canonical-write authorization, or material-update flags onto the original live skip placement.

### 3. Fresh official follow-up stale detection
The shared live/shadow stale-story test no longer requires the literal current weekday when a fresh source headline/teaser contains an explicit completed official finding/status determination such as `NWS confirms`.

The exemption is deliberately narrow. Generic incident verbs such as `arrested` and `charged` do not make a retouched old story fresh by themselves, and forward-looking language such as `will survey` remains distinguishable from a completed finding.

## Observability
Semantic publication-gate output now records:
- `late_published_skip_materiality_decisions`
- summary `late_published_skip_materiality_evaluations`
- summary `late_published_skip_materiality_promotions`

A successful terminal refresh logs:
`LATE MATERIAL UPDATE ROUTE: refreshed canonical page ...`

## Regressions
Added production regressions proving:
1. Old pre-survey tornado canonical + newer NWS EF0/75 mph confirmation -> exact canonical is updated in place.
2. Same-story source with no material new facts -> existing canonical is preserved and composer is not invoked.
3. Failed material-update composition -> original skip placement is unchanged.
4. Fresh `NWS confirms ... Sunday` source remains fresh without the word `Monday`.
5. Fresh feed timestamp alone cannot revive an old incident with no new official development.

## Validation
- Exact workflow-equivalent pytest command: **967 passed**
- Package validation: **38 modules / 119 public exports**
- Python compilation: PASS

## Scope
This increment does not change Sonnet model roles, topic-category adjudication, county routing, Hometown retirement, paywall policy, custom articles, ranking, or permalink identity rules. Apply after v1.13.6.7i.
