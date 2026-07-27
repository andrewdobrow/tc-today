# Category Generation Production Review Guide

Use this guide for the next three normal production runs after deploying v1.11.6.1.

## Files to collect

Send one ZIP containing:

```text
production-log.txt
data/category-generation-report.json
data/editorial_observability.json
data/story-regression-report.json
data/editorial_story_registry.json
```

`presentation-contract.json` and `homepage-ranking-recommendations.json` remain useful but are secondary for this rollout.

## Healthy-run indicators

The production log should show:

```text
TCT Editorial Engine — v1.11.6.1 category-generation-failure-containment
Category generation report: ...
```

For each category it should also show a timing line such as:

```text
Timing: Indian River County 84.2s (model 78.6s; status=generated_live)
```

or a controlled recovery line such as:

```text
Category generation contained for Indian River County: invalid_json (...); using archive recovery
```

A controlled failure should not include an `AttributeError` traceback.

## What to review across three runs

### Reliability

- No null-hero traceback.
- No model attempt exceeds its assigned timeout by a material amount.
- Failed categories recover from the archive and do not block deployment.
- Story regression, identity, permalink, presentation, RSS, and nonstory gates continue to pass.

### Runtime

Compare:

- total generator runtime;
- total `category generation and enrichment` time;
- `category_generation.summary.model_elapsed_seconds`;
- per-category `elapsed_seconds`;
- number of model attempts and retries.

A single malformed category should no longer create an unbounded run.

### Source health

For each category, compare:

- `fetched_candidate_count`;
- `fresh_candidate_count`;
- `publishable_source_count`;
- `selected_source_count`;
- archive recovery frequency.

This will distinguish model reliability problems from feed/source-depth problems.

### Follow-up observability

Continue reviewing:

- current follow-up candidates;
- retrospective candidates;
- clean activation evidence;
- identity conflicts.

v1.11.6.1 does not modify follow-up logic. The extra normal runs are intended to build evidence before any activation decision.

## Decision point after three runs

Proceed to the next optimization only when:

- all publication gates remain stable;
- category failures are contained without tracebacks;
- the report consistently identifies the slow categories;
- no valid category is repeatedly timing out under the default 120/180-second limits.

If valid categories repeatedly hit the budget, tune the limits before reducing model work. If most recoveries are caused by zero publishable sources, the next task should be source expansion rather than model changes.
