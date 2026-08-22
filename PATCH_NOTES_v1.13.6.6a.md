# TCT v1.13.6.6a — Assignment Editor Final-Pipeline Alignment

## Purpose

The first v1.13.6.6 assignment-editor shadow run produced a 4–0 blind preference for the Sonnet 5 assignment editor → Sonnet 4.5 writer architecture, but the review artifact exposed an experiment-integrity flaw: the "current production" side was captured from the raw Sonnet 4.5 category response before deterministic post-generation corrections. The live site had already changed some of those heroes through freshness and publication guards, so the two variants were not being compared at the same pipeline stage.

This release fixes the experiment only. Live publication behavior remains unchanged.

## Final-pipeline comparison contract

For every queued category, the experiment now preserves four distinct objects:

- `raw_baseline_output` — raw successful production model output captured before deterministic correction;
- `final_baseline_output` — projection of the actual final live category after the normal production pipeline has completed;
- `raw_challenger_output` — Sonnet 5 assignment editor → Sonnet 4.5 writer output before alignment;
- `final_challenger_output` — publication-isolated shadow output after deterministic alignment.

The blind review uses **only** `final_baseline_output` and `final_challenger_output`. Raw objects remain available only in the machine report for diagnosis.

## Shadow deterministic alignment

The shadow copy is processed after the live build and receives the same shared deterministic constraints relevant to category publication:

- source provenance attachment;
- category membership/eligibility authority;
- urgency decay and age caps;
- stale-hero replacement logic;
- contextual-update lead validation;
- universal article-framing validation;
- publication-depth/quality checks;
- current-run story identity stamping;
- published-story skip suppression using the pre-generation archive snapshot;
- county-membership authority;
- final canonical identity rebinding and within-category canonical deduplication.

If those rules eliminate the shadow hero, the experiment uses the actual final production deterministic recovery hero. This prevents a shadow model from receiving credit for copy that production itself would have rejected.

## Final production projection

The production comparison is taken from the actual final `all_categories` object after normal publication processing. Deterministic archive filler cards are omitted from the blind comparison so scoring remains focused on the current source packet. A deterministic archive-recovery hero is retained when it is the category's real final lead.

## Publication isolation

The experiment still runs only after the normal build, contracts, caches, archive writes, RSS, static pages, and observability are complete. It operates on deep copies and does not append to or replace live categories, write the generation cache, change archive/story identity state, or alter published pages.

## Artifacts

Existing artifact names are retained:

- `data/assignment-editor-shadow-report.json`
- `data/assignment-editor-shadow-review.md`
- `data/assignment-editor-shadow-answer-key.json`
- `data/model-usage-report.json`

The report schema is now version 2 and includes raw-vs-final comparison diagnostics. The answer key marks the comparison stage as `final_pipeline_aligned`.

## Validation

- Alignment/category/canonical focused suite: **135 passed**
- Workflow-equivalent suite: **931 passed**
- Existing warnings: **43** (`datetime.utcnow()` deprecations; unchanged)
- Package validation: **38 modules / 119 public exports**
- Generator runtime guard: **PASS**
- False-jurisdiction source guard: **PASS**
